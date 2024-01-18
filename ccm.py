#!/usr/bin/env python3

from typing import TYPE_CHECKING, List, Tuple, Dict, Optional
from enum import Enum
import time
import argparse

try:
  from core.api.grpc import client # type: ignore
  from core.api.grpc.core_pb2 import LinkType, Link # type: ignore
except ImportError:
  print("Error importing core emu, please install core emu.")
  exit(1)

class ContactState(Enum):
  """Contact state enumeration.
  """
  PRE = 0
  LIVE = 1
  POST = 2

class CoreContact(object):
  def __init__(self, timespan : Tuple[int, int], nodes : Tuple[int, int], bw : int, loss : float, delay : float, jitter : float) -> None:
      self.timespan = timespan
      self.nodes = nodes
      self.bw = bw
      self.loss = loss
      self.delay = delay
      self.jitter = jitter

  def __str__(self) -> str:
    return "CoreContact(timespan=%r, nodes=%r, bw=%d, loss=%f, delay=%f, jitter=%f)" % (self.timespan, self.nodes, self.bw, self.loss, self.delay, self.jitter)
  
  @classmethod
  def from_string(cls, line : str) -> 'CoreContact':
    line = line.strip()
    if line.startswith('a contact'):
      line = line[9:].strip()
    fields = line.split()
    print(fields, len(fields))
    if len(fields) != 8:
      raise ValueError("Invalid CoreContact line: %s" % line)
    timespan = (int(fields[0]), int(fields[1]))
    nodes = (int(fields[2]), int(fields[3]))
    bw = int(fields[4])
    loss = float(fields[5])
    delay = int(fields[6])
    jitter = int(fields[7])
    return cls(timespan, nodes, bw, loss, delay, jitter)

class CoreContactPlan(object):
    """A CoreContactPlan file.
    """

    def __init__(self, filename : str = None, contacts : Dict[CoreContact, ContactState] = {}) -> None:
        self.loop = False
        self.contacts = contacts
        if filename:
            self.load(filename)

    def __str__(self) -> str:
      return "CoreContactPlan(loop=%r, #contacts=%d)" % (self.loop, len(self.contacts))
       
    def load(self, filename : str) -> None:
        contacts = {}
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                fields = line.split()
                if len(fields) == 3 and fields[0] == 's':
                  if fields[1] == 'loop':
                      if fields[2] == '1':
                        self.loop = True
                      else:
                        self.loop = False
                elif len(fields) > 4 and fields[0] == 'a':
                  if fields[1] == 'contact':
                    contact = CoreContact.from_string(line)
                    print(contact)
                    contacts[contact] = ContactState.PRE
        self.contacts = contacts
    
    def at(self, time : int) -> List[Tuple[CoreContact, ContactState]]:
      """Returns the list of contacts at the given time.
      """
      return [(c,s) for c, s in self.contacts.items() if c.timespan[0] <= time and c.timespan[1] >= time]

    def need_activation(self, time : int) -> List[Tuple[CoreContact, ContactState]]:
      """Returns the list of contacts at the given time that need to be activated.
      """
      all = self.at(time)
      return [(c,s) for (c, s) in all if s == ContactState.PRE]
    
    def need_deactivation(self, time : int) -> List[Tuple[CoreContact, ContactState]]:
      """Returns the list of contacts at the given time that need to be deactivated.
      """
      return  [(c,s) for c, s in self.contacts.items() if time >= c.timespan[1] and s == ContactState.LIVE]
    
    def next_activation(self, time : int) -> Optional[int]:
      """Returns the next activation time.
      """
      activations = [c.timespan[0] for c, s in self.contacts.items() if s == ContactState.PRE and c.timespan[0] >= time]
      if len(activations) == 0:
        return None
      return min(activations)
    
    def next_deactivation(self, time : int) -> Optional[int]:
      """Returns the next deactivation time.
      """
      deactivations = [c.timespan[1] for c, s in self.contacts.items() if s == ContactState.LIVE and c.timespan[1] >= time]
      if len(deactivations) == 0:
        return None
      return min(deactivations)
    
    def reset(self) -> None:
      """Resets the contact plan to its initial state.
      """
      for c in self.contacts:
        self.contacts[c] = ContactState.PRE


def find_link(links : List[Link], node1 : int, node2 : int) -> Optional[Link]:
  for link in links:
    if (link.node1_id == node1 and link.node2_id == node2) or (link.node1_id == node2 and link.node2_id == node1):
      return link
  return None

parser = argparse.ArgumentParser(description='CCM: Core Contact Manager')
parser.add_argument('file', metavar='FILE', type=str, help='Core Contact Plan file to load')
parser.add_argument('-s', '--session', metavar='ID', type=int, help='Session ID to use', default=1)
parser.add_argument('-l', '--loop', metavar='LOOP', type=bool, help='Override looping')

args = parser.parse_args()

cp = CoreContactPlan(args.file)

cur_time : int = 0
sess_id : int = args.session

core = client.CoreGrpcClient()
core.connect()
session = core.get_session(sess_id)
links = session.links
nodes = session.nodes

while True:
  if cp.next_activation(cur_time) == None and cp.next_deactivation(cur_time) == None:
    if cp.loop or args.loop:
      print("Looping")
      cur_time = 0
      cp.reset()
      continue
    else:
      print("No more events")
      break

  next_event = min([t for t in [cp.next_activation(cur_time), cp.next_deactivation(cur_time)] if t is not None])
  
  print("[ %d ] Next event(s) at %d" % (cur_time, next_event))
  sleep_time = next_event - cur_time
  time.sleep(sleep_time)
  cur_time = next_event
  for contact, state in cp.need_activation(cur_time):
    print("[ %d ] Activating %s" % (cur_time, contact))
    node1 = contact.nodes[0]
    node2 = contact.nodes[1]
    link = find_link(links, node1, node2)
    if link is None:
      print("WARNING: Link not found for %d, %d" % (node1, node2))
      continue
    link.options.bandwidth = contact.bw
    link.options.delay = contact.delay
    link.options.loss = contact.loss
    link.options.jitter = contact.jitter
    core.edit_link(sess_id, link, None)

    cp.contacts[contact] = ContactState.LIVE
  
  for contact, state in cp.need_deactivation(cur_time):
    print("[ %d ] Deactivating %s" % (cur_time, contact))
    node1 = contact.nodes[0]
    node2 = contact.nodes[1]
    link = find_link(links, node1, node2)
    if link is None:
      print("WARNING: Link not found for %d, %d" % (node1, node2))
      continue
    link.options.loss = 100
    core.edit_link(sess_id, link, None)
    cp.contacts[contact] = ContactState.POST

