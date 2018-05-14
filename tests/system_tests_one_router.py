#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#

from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
from __future__ import print_function

import unittest2 as unittest
from proton import Condition, Message, Delivery, PENDING, ACCEPTED, REJECTED, Url, symbol, Timeout
from system_test import TestCase, Qdrouterd, main_module, TIMEOUT
from proton.handlers import MessagingHandler, TransactionHandler
from proton.reactor import Container, AtMostOnce, AtLeastOnce, DynamicNodeProperties, LinkOption, ApplicationEvent, EventInjector
from proton.utils import BlockingConnection, SyncRequestResponse
from qpid_dispatch.management.client import Node

CONNECTION_PROPERTIES_UNICODE_STRING = {u'connection': u'properties', u'int_property': 6451}
CONNECTION_PROPERTIES_SYMBOL = dict()
CONNECTION_PROPERTIES_SYMBOL[symbol("connection")] = symbol("properties")
CONNECTION_PROPERTIES_BINARY = {b'client_identifier': b'policy_server'}


#====================================================
# Helper classes for all tests.
#====================================================


# Named timers allow test code to distinguish between several
# simultaneous timers, going off at different rates.
class MultiTimeout ( object ):
    def __init__(self, parent, name):
        self.parent = parent
        self.name   = name

    def on_timer_task(self, event):
        self.parent.timeout ( self.name )




class OneRouterTest(TestCase):
    """System tests involving a single router"""
    @classmethod
    def setUpClass(cls):
        """Start a router and a messenger"""
        super(OneRouterTest, cls).setUpClass()
        name = "test-router"
        OneRouterTest.listen_port = cls.tester.get_port()
        config = Qdrouterd.Config([
            ('router', {'mode': 'standalone', 'id': 'QDR', 'allowUnsettledMulticast': 'yes'}),

            # Setting the stripAnnotations to 'no' so that the existing tests will work.
            # Setting stripAnnotations to no will not strip the annotations and any tests that were already in this file
            # that were expecting the annotations to not be stripped will continue working.
            ('listener', {'port': OneRouterTest.listen_port, 'maxFrameSize': '2048', 'stripAnnotations': 'no'}),

            # The following listeners were exclusively added to test the stripAnnotations attribute in qdrouterd.conf file
            # Different listeners will be used to test all allowed values of stripAnnotations ('no', 'both', 'out', 'in')
            ('listener', {'port': cls.tester.get_port(), 'maxFrameSize': '2048', 'stripAnnotations': 'no'}),
            ('listener', {'port': cls.tester.get_port(), 'maxFrameSize': '2048', 'stripAnnotations': 'both'}),
            ('listener', {'port': cls.tester.get_port(), 'maxFrameSize': '2048', 'stripAnnotations': 'out'}),
            ('listener', {'port': cls.tester.get_port(), 'maxFrameSize': '2048', 'stripAnnotations': 'in'}),

            ('address', {'prefix': 'closest', 'distribution': 'closest'}),
            ('address', {'prefix': 'balanced', 'distribution': 'balanced'}),
            ('address', {'prefix': 'multicast', 'distribution': 'multicast'}),
            ('address', {'prefix': 'unavailable', 'distribution': 'unavailable'})
        ])
        cls.router = cls.tester.qdrouterd(name, config)
        cls.router.wait_ready()
        cls.address = cls.router.addresses[0]
        cls.closest_count = 1

        cls.no_strip_addr   = cls.router.addresses[1]
        cls.both_strip_addr = cls.router.addresses[2]
        cls.out_strip_addr  = cls.router.addresses[3]
        cls.in_strip_addr   = cls.router.addresses[4]


    def test_01_listen_error(self):
        # Make sure a router exits if a initial listener fails, doesn't hang.
        config = Qdrouterd.Config([
            ('router', {'mode': 'standalone', 'id': 'bad'}),
            ('listener', {'port': OneRouterTest.listen_port})])
        r = Qdrouterd(name="expect_fail", config=config, wait=False)
        self.assertEqual(1, r.wait())


    def test_02_pre_settled ( self ):
        addr = self.address + '/closest/' + str(OneRouterTest.closest_count)
        OneRouterTest.closest_count += 1
        test = PreSettled ( addr, n_messages = 10 )
        test.run ( )
        self.assertEqual ( None, test.error )


    def test_03_multicast_unsettled ( self ) :
        n_receivers = 5
        addr = self.address + '/multicast/1'
        test = MulticastUnsettled ( addr, n_messages = 10, n_receivers = 5 )
        test.run ( )
        self.assertEqual ( None, test.error )


    def test_04_disposition_returns_to_closed_connection ( self ) :
        addr = self.address + '/closest/' + str(OneRouterTest.closest_count)
        OneRouterTest.closest_count += 1
        test = DispositionReturnsToClosedConnection ( addr, n_messages = 100 )
        test.run ( )
        self.assertEqual ( None, test.error )


    def test_05_sender_settles_first ( self ) :
        addr = self.address + '/closest/' + str(OneRouterTest.closest_count)
        OneRouterTest.closest_count += 1
        test = SenderSettlesFirst ( addr, n_messages = 100 )
        test.run ( )
        self.assertEqual ( None, test.error )


    def test_06_propagated_disposition ( self ) :
        addr = self.address + '/closest/' + str(OneRouterTest.closest_count)
        OneRouterTest.closest_count += 1
        test = PropagatedDisposition ( addr, n_messages = 10 )
        test.run ( )
        self.assertEqual ( None, test.error )


    def test_07_unsettled_undeliverable ( self ) :
        addr = self.address + '/closest/' + str(OneRouterTest.closest_count)
        OneRouterTest.closest_count += 1
        test = UsettledUndeliverable ( addr, n_messages = 10 )
        test.run ( )
        self.assertEqual ( None, test.error )


    def test_08_three_ack ( self ) :
        addr = self.address + '/closest/' + str(OneRouterTest.closest_count)
        OneRouterTest.closest_count += 1
        test = ThreeAck ( addr, n_messages = 10 )
        test.run ( )
        self.assertEqual ( None, test.error )


    def test_09_message_annotations ( self ) :
        addr = self.address + '/closest/' + str(OneRouterTest.closest_count)
        OneRouterTest.closest_count += 1
        test = MessageAnnotations ( addr, n_messages = 10 )
        test.run ( )
        self.assertEqual ( None, test.error )


    # Tests stripping of ingress and egress annotations.
    # There is a property in qdrouter.json called stripAnnotations with possible values of ["in", "out", "both", "no"]
    # The default for stripAnnotations is "both" (which means strip annotations on both ingress and egress)
    # This test will test the stripAnnotations = no option - meaning no annotations must be stripped.
    # We will send in a custom annotation and make sure that we get back 3 annotations on the received message
    def test_10_strip_message_annotations_custom(self):
        addr = self.no_strip_addr + "/strip_message_annotations_no_custom/1"
        OneRouterTest.closest_count += 1
        test = StripMessageAnnotationsCustom ( addr, n_messages = 10 )
        test.run ( )
        self.assertEqual ( None, test.error )


    # stripAnnotations property is set to "no" 
    def test_11_test_strip_message_annotations_no(self):
        addr = self.no_strip_addr + "/strip_message_annotations_no/1"
        test = StripMessageAnnotationsNo ( addr, n_messages = 10 )
        test.run ( )
        self.assertEqual ( None, test.error )


    # stripAnnotations property is set to "no"
    def test_12_test_strip_message_annotations_no_add_trace(self):
        addr = self.no_strip_addr + "/strip_message_annotations_no_add_trace/1"
        test = StripMessageAnnotationsNoAddTrace ( addr, n_messages = 10 )
        test.run ( )
        self.assertEqual ( None, test.error )


    # Dont send any pre-existing ingress or trace annotations. Make sure that there 
    # are no outgoing message annotations stripAnnotations property is set to "both".
    # Custom annotations, however, are not stripped.
    def test_13_test_strip_message_annotations_both(self):
        addr = self.both_strip_addr + "/strip_message_annotations_both/1"
        test = StripMessageAnnotationsBoth ( addr, n_messages = 10 )
        test.run ( )
        self.assertEqual ( None, test.error )


    # Dont send any pre-existing ingress or trace annotations. Make sure that there 
    # are no outgoing message annotations
    # stripAnnotations property is set to "out"
    def test_14_test_strip_message_annotations_out(self):
        addr = self.out_strip_addr + "/strip_message_annotations_out/1"
        test = StripMessageAnnotationsOut ( addr, n_messages = 10 )
        test.run ( )
        self.assertEqual ( None, test.error )


    # Send in pre-existing trace and ingress and annotations and make sure 
    # that they are not in the outgoing annotations.
    # stripAnnotations property is set to "in"
    def test_15_test_strip_message_annotations_in(self):
        addr = self.in_strip_addr + "/strip_message_annotations_in/1"
        test = StripMessageAnnotationsIn ( addr, n_messages = 10 )
        test.run ( )
        self.assertEqual ( None, test.error )


    def test_16_management(self):
        test = ManagementTest(self.address)
        test.run()
        self.assertEqual(None, test.error)

    def test_17_management_get_operations(self):
        test = ManagementGetOperationsTest(self.address)
        test.run()
        self.assertEqual(None, test.error)

    def test_18_management_not_implemented(self):
        test = ManagementNotImplemented(self.address)
        test.run()
        self.assertEqual(None, test.error)

    def test_19_semantics_multicast(self):
        test = SemanticsMulticast(self.address)
        test.run()
        self.assertEqual(None, test.error)

    def test_20_semantics_closest(self):
        test = SemanticsClosest(self.address)
        test.run()
        self.assertEqual(None, test.error)

    def test_21_semantics_balanced(self):
        test = SemanticsBalanced(self.address)
        test.run()
        self.assertEqual(None, test.error)

    def test_22_to_override(self):
        test = MessageAnnotaionsPreExistingOverride(self.address)
        test.run()

    def test_23_send_settle_mode_settled(self):
        """
        The receiver sets a snd-settle-mode of settle thus indicating that it wants to receive settled messages from
        the sender. This tests make sure that the delivery that comes to the receiver comes as already settled.
        """
        send_settle_mode_test = SndSettleModeTest(self.address)
        send_settle_mode_test.run()
        self.assertTrue(send_settle_mode_test.message_received)
        self.assertTrue(send_settle_mode_test.delivery_already_settled)

    def test_24_excess_deliveries_released(self):
        """
        Message-route a series of deliveries where the receiver provides credit for a subset and
        once received, closes the link.  The remaining deliveries should be released back to the sender.
        """
        test = ExcessDeliveriesReleasedTest(self.address)
        test.run()
        self.assertEqual(None, test.error)

    def test_25_multicast_unsettled(self):
        test = MulticastUnsettledTest(self.address)
        test.run()
        self.assertEqual(None, test.error)

    # Will uncomment this test once https://issues.apache.org/jira/browse/PROTON-1514 is fixed
    #def test_17_multiframe_presettled(self):
    #    test = MultiframePresettledTest(self.address)
    #    test.run()
    #    self.assertEqual(None, test.error)

    def test_26_multicast_no_receivcer(self):
        test = MulticastUnsettledNoReceiverTest(self.address)
        test.run()
        self.assertEqual(None, test.error)

    def test_27_released_vs_modified(self):
        test = ReleasedVsModifiedTest(self.address)
        test.run()
        self.assertEqual(None, test.error)

    def test_28_appearance_of_balance(self):
        test = AppearanceOfBalanceTest(self.address)
        test.run()
        self.assertEqual(None, test.error)

    def test_29_batched_settlement(self):
        test = BatchedSettlementTest(self.address)
        test.run()
        self.assertEqual(None, test.error)
        self.assertTrue(test.accepted_count_match)

    def test_30_presettled_overflow(self):
        test = PresettledOverflowTest(self.address)
        test.run()
        self.assertEqual(None, test.error)

    def test_31_create_unavailable_sender(self):
        test = UnavailableSender(self.address)
        test.run()
        self.assertTrue(test.passed)

    def test_32_create_unavailable_receiver(self):
        test = UnavailableReceiver(self.address)
        test.run()
        self.assertTrue(test.passed)

    def test_33_large_streaming_test(self):
        test = LargeMessageStreamTest(self.address)
        test.run()
        self.assertEqual(None, test.error)

    def test_34_reject_coordinator(self):
        test = RejectCoordinatorTest(self.address)
        test.run()
        self.assertTrue(test.passed)

    def test_35_reject_disposition(self):
        test = RejectDispositionTest(self.address)
        test.run()
        self.assertTrue(test.received_error)
        self.assertTrue(test.reject_count_match)

    def test_37_connection_properties_unicode_string(self):
        """
        Tests connection property that is a map of unicode strings and integers
        """
        connection = BlockingConnection(self.router.addresses[0],
                                        timeout=60,
                                        properties=CONNECTION_PROPERTIES_UNICODE_STRING)
        client = SyncRequestResponse(connection)

        node = Node.connect(self.router.addresses[0])

        results = node.query(type='org.apache.qpid.dispatch.connection', attribute_names=[u'properties']).results

        found = False
        for result in results:
            if u'connection' in result[0] and u'int_property' in result[0]:
                found = True
                self.assertEqual(result[0][u'connection'], u'properties')
                self.assertEqual(result[0][u'int_property'], 6451)

        self.assertTrue(found)
        client.connection.close()

    def test_38_connection_properties_symbols(self):
        """
        Tests connection property that is a map of symbols
        """
        connection = BlockingConnection(self.router.addresses[0],
                                        timeout=60,
                                        properties=CONNECTION_PROPERTIES_SYMBOL)
        client = SyncRequestResponse(connection)

        node = Node.connect(self.router.addresses[0])

        results = node.query(type='org.apache.qpid.dispatch.connection', attribute_names=[u'properties']).results

        found = False
        for result in results:
            if u'connection' in result[0]:
                if result[0][u'connection'] == u'properties':
                    found = True
                    break

        self.assertTrue(found)

        client.connection.close()

    def test_39_connection_properties_binary(self):
        """
        Tests connection property that is a binary map. The router ignores AMQP binary data type.
        Router should not return anything for connection properties
        """
        connection = BlockingConnection(self.router.addresses[0],
                                        timeout=60,
                                        properties=CONNECTION_PROPERTIES_BINARY)
        client = SyncRequestResponse(connection)

        node = Node.connect(self.router.addresses[0])

        results = node.query(type='org.apache.qpid.dispatch.connection', attribute_names=[u'properties']).results

        results_found = True

        for result in results:
            if not result[0]:
                results_found = False
            else:
                results_found = True
                break

        self.assertFalse(results_found)

        client.connection.close()


class SemanticsClosest(MessagingHandler):
    def __init__(self, address):
        super(SemanticsClosest, self).__init__()
        self.address = address
        self.dest = "closest.1"
        self.timer = None
        self.conn = None
        self.sender = None
        self.receiver_a = None
        self.receiver_b = None
        self.receiver_c = None
        self.num_messages = 100
        self.n_received_a = 0
        self.n_received_b = 0
        self.n_received_c = 0
        self.error = None
        self.n_sent = 0
        self.rx_set = []

    def on_start(self, event):
        self.timer = event.reactor.schedule(TIMEOUT, Timeout(self))
        self.conn = event.container.connect(self.address)
        self.sender = event.container.create_sender(self.conn, self.dest)
        # Receiver on same router as the sender must receive all the messages. The other two
        # receivers are on the other router
        self.receiver_a = event.container.create_receiver(self.conn, self.dest, name="A")
        self.receiver_b = event.container.create_receiver(self.conn, self.dest, name="B")
        self.receiver_c = event.container.create_receiver(self.conn, self.dest, name="C")

    def timeout(self):
        self.error = "Timeout Expired: sent=%d rcvd=%d/%d/%d" % \
                     (self.n_sent, self.n_received_a, self.n_received_b, self.n_received_c)
        self.conn.close()

    def check_if_done(self):
        if self.n_received_a + self.n_received_b + self.n_received_c == self.num_messages\
                and self.n_received_b != 0 and self.n_received_c != 0:
            self.rx_set.sort()
            #print self.rx_set
            all_messages_received = True
            for i in range(self.num_messages):
                if not i == self.rx_set[i]:
                    all_messages_received = False

            if all_messages_received:
                self.timer.cancel()
                self.conn.close()

    def on_sendable(self, event):
        if self.n_sent < self.num_messages:
            msg = Message(body={'number': self.n_sent})
            self.sender.send(msg)
            self.n_sent += 1

    def on_message(self, event):
        if event.receiver == self.receiver_a:
            self.n_received_a += 1
            self.rx_set.append(event.message.body['number'])
        if event.receiver == self.receiver_b:
            self.n_received_b += 1
            self.rx_set.append(event.message.body['number'])
        if event.receiver == self.receiver_c:
            self.n_received_c += 1
            self.rx_set.append(event.message.body['number'])

    def on_accepted(self, event):
        self.check_if_done()

    def run(self):
        Container(self).run()


class MessageAnnotaionsPreExistingOverride(MessagingHandler):
    def __init__(self, address):
        super(MessageAnnotaionsPreExistingOverride, self).__init__()
        self.address = address
        self.dest = "toov/1"
        self.error = "Pre-existing x-opt-qd.to has been stripped"
        self.timer = None
        self.conn = None
        self.sender = None
        self.receiver = None
        self.msg_not_sent = True

    def on_start(self, event):
        self.timer = event.reactor.schedule(TIMEOUT, Timeout(self))
        self.conn = event.container.connect(self.address)
        self.sender = event.container.create_sender(self.conn, self.dest)
        self.receiver = event.container.create_receiver(self.conn, self.dest)

    def timeout(self):
        self.error = "Timeout Expired: Sent message not received"
        self.conn.close()

    def bail(self, message):
        self.error = message
        self.conn.close()
        self.timer.cancel()

    def on_sendable(self, event):
        if self.msg_not_sent:
            msg = Message(body={'number': 0})
            msg.annotations = {'x-opt-qd.to': 'toov/1'}
            event.sender.send(msg)
            self.msg_not_sent = False

    def on_message(self, event):
        if 0 == event.message.body['number']:
            ma = event.message.annotations
            if ma['x-opt-qd.to'] == 'toov/1':
                self.bail(None)
            else:
                self.bail("Pre-existing x-opt-qd.to has been stripped")
        else:
            self.bail("body does not match with the sent message body")

    def run(self):
        Container(self).run()


class SemanticsMulticast(MessagingHandler):
    def __init__(self, address):
        super(SemanticsMulticast, self).__init__()
        self.address = address
        self.dest = "multicast.2"
        self.error = None
        self.n_sent = 0
        self.count = 3
        self.n_received_a = 0
        self.n_received_b = 0
        self.n_received_c = 0
        self.timer = None
        self.conn = None
        self.sender = None
        self.receiver_a = None
        self.receiver_b = None
        self.receiver_c = None

    def on_start(self, event):
        self.timer = event.reactor.schedule(TIMEOUT, Timeout(self))
        self.conn = event.container.connect(self.address)
        self.sender = event.container.create_sender(self.conn, self.dest)
        self.receiver_a = event.container.create_receiver(self.conn, self.dest, name="A")
        self.receiver_b = event.container.create_receiver(self.conn, self.dest, name="B")
        self.receiver_c = event.container.create_receiver(self.conn, self.dest, name="C")

    def timeout(self):
        self.error = "Timeout Expired: sent=%d rcvd=%d/%d/%d" % \
                     (self.n_sent, self.n_received_a, self.n_received_b, self.n_received_c)
        self.conn.close()

    def check_if_done(self):
        if self.n_received_a + self.n_received_b + self.n_received_c == self.count and \
                self.n_received_a == self.n_received_b and self.n_received_c == self.n_received_b:
            self.timer.cancel()
            self.conn.close()

    def on_sendable(self, event):
        if self.n_sent == 0:
            msg = Message(body="SemanticsMulticast-Test")
            self.sender.send(msg)
            self.n_sent += 1

    def on_message(self, event):
        if event.receiver == self.receiver_a:
            self.n_received_a += 1
        if event.receiver == self.receiver_b:
            self.n_received_b += 1
        if event.receiver == self.receiver_c:
            self.n_received_c += 1

    def on_accepted(self, event):
        self.check_if_done()

    def run(self):
        Container(self).run()


class ManagementNotImplemented(MessagingHandler):
    def __init__(self, address):
        super(ManagementNotImplemented, self).__init__()
        self.address = address
        self.timer = None
        self.conn = None
        self.sender = None
        self.receiver = None
        self.sent_count = 0
        self.error = None
        self.num_messages = 0

    def timeout(self):
        self.error = "No response received for management request"
        self.conn.close()

    def bail(self, message):
        self.error = message
        self.conn.close()
        self.timer.cancel()

    def on_start(self, event):
        self.timer = event.reactor.schedule(TIMEOUT, Timeout(self))
        self.conn = event.container.connect(self.address)
        self.sender = event.container.create_sender(self.conn)
        self.receiver = event.container.create_receiver(self.conn, None, dynamic=True)

    def on_sendable(self, event):
        if self.num_messages < 1:
            request = Message()
            request.address = "amqp:/_local/$management"
            request.reply_to = self.receiver.remote_source.address
            request.properties = {u'type':u'org.amqp.management', u'name':u'self', u'operation':u'NOT-IMPL'}

            event.sender.send(request)
            self.num_messages += 1

    def run(self):
        Container(self).run()

    def on_message(self, event):
        if event.receiver == self.receiver:
            if event.message.properties['statusCode'] == 501:
                self.bail(None)
            else:
                self.bail("The return status code is %s. It should be 501" % str(event.message.properties['statusCode']))


class ManagementGetOperationsTest(MessagingHandler):
    def __init__(self, address):
        super(ManagementGetOperationsTest, self).__init__()
        self.address = address
        self.timer = None
        self.conn = None
        self.sender = None
        self.receiver = None
        self.sent_count = 0
        self.error = None
        self.num_messages = 0

    def timeout(self):
        self.error = "No response received for management request"
        self.conn.close()

    def bail(self, message):
        self.error = message
        self.conn.close()
        self.timer.cancel()

    def on_start(self, event):
        self.timer = event.reactor.schedule(TIMEOUT, Timeout(self))
        self.conn = event.container.connect(self.address)
        self.sender = event.container.create_sender(self.conn)
        self.receiver = event.container.create_receiver(self.conn, None, dynamic=True)

    def on_sendable(self, event):
        if self.num_messages < 1:
            request = Message()
            request.address = "amqp:/_local/$management"
            request.reply_to = self.receiver.remote_source.address
            request.properties = {u'type':u'org.amqp.management', u'name':u'self', u'operation':u'GET-OPERATIONS'}

            event.sender.send(request)
            self.num_messages += 1

    def run(self):
        Container(self).run()

    def on_message(self, event):
        if event.receiver == self.receiver:
            if event.message.properties['statusCode'] == 200:
                if 'org.apache.qpid.dispatch.router' in event.message.body.keys():
                    if len(event.message.body.keys()) > 2:
                        self.bail(None)
                    else:
                        self.bail('size of keys in message body less than or equal 2')
                else:
                    self.bail('org.apache.qpid.dispatch.router is not in the keys')
            else:
                self.bail("The return status code is %s. It should be 200" % str(event.message.properties['statusCode']))


class ManagementTest(MessagingHandler):
    def __init__(self, address):
        super(ManagementTest, self).__init__()
        self.address = address
        self.timer = None
        self.conn = None
        self.sender = None
        self.receiver = None
        self.sent_count = 0
        self.msg_not_sent = True
        self.error = None
        self.num_messages = 0
        self.response1 = False
        self.response2 = False

    def timeout(self):
        if not self.response1:
            self.error = "Incorrect response received for message with correlation id C1"
        if not self.response1:
            self.error = self.error + "and incorrect response received for message with correlation id C2"
        self.conn.close()

    def on_start(self, event):
        self.timer = event.reactor.schedule(TIMEOUT, Timeout(self))
        self.conn = event.container.connect(self.address)
        self.sender = event.container.create_sender(self.conn)
        self.receiver = event.container.create_receiver(self.conn, None, dynamic=True)

    def on_sendable(self, event):
        if self.num_messages < 2:
            request = Message()
            request.address = "amqp:/$management"
            request.reply_to = self.receiver.remote_source.address
            request.correlation_id = "C1"
            request.properties = {u'type': u'org.amqp.management', u'name': u'self', u'operation': u'GET-MGMT-NODES'}

            event.sender.send(request)
            self.num_messages += 1

            request = Message()
            request.address = "amqp:/_topo/0/QDR.B/$management"
            request.correlation_id = "C2"
            request.reply_to = self.receiver.remote_source.address
            request.properties = {u'type': u'org.amqp.management', u'name': u'self', u'operation': u'GET-MGMT-NODES'}
            event.sender.send(request)
            self.num_messages += 1

    def on_message(self, event):
        if event.receiver == self.receiver:
            if event.message.correlation_id == "C1":
                if event.message.properties['statusCode'] == 200 and \
                        event.message.properties['statusDescription'] is not None \
                        and event.message.body == []:
                    self.response1 = True
            elif event.message.correlation_id == "C2":
                if event.message.properties['statusCode'] == 200 and \
                        event.message.properties['statusDescription'] is not None \
                        and event.message.body == []:
                    self.response2 = True

        if self.response1 and self.response2:
            self.error = None

        if self.error is None:
            self.timer.cancel()
            self.conn.close()

    def run(self):
        Container(self).run()



class CustomTimeout(object):
    def __init__(self, parent):
        self.parent = parent

    def addr_text(self, addr):
        if not addr:
            return ""
        if addr[0] == 'M':
            return addr[2:]
        else:
            return addr[1:]

    def on_timer_task(self, event):
        local_node = Node.connect(self.parent.address, timeout=TIMEOUT)

        res = local_node.query('org.apache.qpid.dispatch.router.address')
        name = res.attribute_names.index('name')
        found = False
        for results in res.results:
            if "balanced.1" == self.addr_text(results[name]):
                found = True
                break

        if found:
            self.parent.cancel_custom()
            self.parent.create_sender(event)

        else:
            event.reactor.schedule(2, self)


class SemanticsBalanced(MessagingHandler):
    def __init__(self, address):
        super(SemanticsBalanced, self).__init__(auto_accept=False, prefetch=0)
        self.address = address
        self.dest = "balanced.1"
        self.timer = None
        self.conn = None
        self.sender = None
        self.receiver_a = None
        self.receiver_b = None
        self.receiver_c = None
        self.num_messages = 250
        self.n_received_a = 0
        self.n_received_b = 0
        self.n_received_c = 0
        self.error = None
        self.n_sent = 0
        self.rx_set = []
        self.custom_timer = None

    def on_start(self, event):
        self.timer = event.reactor.schedule(TIMEOUT, Timeout(self))
        self.custom_timer = event.reactor.schedule(2, CustomTimeout(self))
        self.conn = event.container.connect(self.address)

        # This receiver is on the same router as the sender
        self.receiver_a = event.container.create_receiver(self.conn, self.dest, name="A")

        # These two receivers are connected to a different router than the sender
        self.receiver_b = event.container.create_receiver(self.conn, self.dest, name="B")
        self.receiver_c = event.container.create_receiver(self.conn, self.dest, name="C")

        self.receiver_a.flow(100)
        self.receiver_b.flow(100)
        self.receiver_c.flow(100)

    def cancel_custom(self):
        self.custom_timer.cancel()

    def create_sender(self, event):
        self.sender = event.container.create_sender(self.conn, self.dest)

    def timeout(self):
        self.error = "Timeout Expired: sent=%d rcvd=%d/%d/%d" % \
                     (self.n_sent, self.n_received_a, self.n_received_b, self.n_received_c)
        self.conn.close()

    def check_if_done(self):
        if self.n_received_a + self.n_received_b + self.n_received_c == self.num_messages and \
                self.n_received_a > 0 and self.n_received_b > 0 and self.n_received_c > 0:
            self.rx_set.sort()
            all_messages_received = True
            for i in range(self.num_messages):
                if not i == self.rx_set[i]:
                    all_messages_received = False

            if all_messages_received:
                self.timer.cancel()
                self.conn.close()

    def on_sendable(self, event):
        if self.n_sent < self.num_messages:
            msg = Message(body={'number': self.n_sent})
            self.sender.send(msg)
            self.n_sent += 1

    def on_message(self, event):
        if event.receiver == self.receiver_a:
            self.n_received_a += 1
            self.rx_set.append(event.message.body['number'])
        elif event.receiver == self.receiver_b:
            self.n_received_b += 1
            self.rx_set.append(event.message.body['number'])
        elif event.receiver == self.receiver_c:
            self.n_received_c += 1
            self.rx_set.append(event.message.body['number'])

        self.check_if_done()

    def run(self):
        Container(self).run()


class Timeout(object):
    def __init__(self, parent):
        self.parent = parent

    def on_timer_task(self, event):
        self.parent.timeout()


class PreSettled ( MessagingHandler ) :
    def __init__ ( self,
                   addr,
                   n_messages
                 ) :
        super ( PreSettled, self ) . __init__ ( prefetch = n_messages )
        self.addr       = addr
        self.n_messages = n_messages

        self.sender     = None
        self.receiver   = None
        self.n_sent     = 0
        self.n_received = 0
        self.error      = None
        self.test_timer = None


    def run ( self ) :
        Container(self).run()


    def bail ( self, travail ) :
        self.error = travail
        self.send_conn.close ( )
        self.recv_conn.close ( )
        self.test_timer.cancel ( )


    def timeout ( self, name ):
        self.bail ( "Timeout Expired: %d messages received, %d expected." % (self.n_received, self.n_messages) )


    def on_start ( self, event ):
        self.send_conn = event.container.connect ( self.addr )
        self.recv_conn = event.container.connect ( self.addr )

        self.sender   = event.container.create_sender   ( self.send_conn, self.addr )
        self.receiver = event.container.create_receiver ( self.send_conn, self.addr )
        self.receiver.flow ( self.n_messages )
        self.test_timer  = event.reactor.schedule ( 15, MultiTimeout(self, "test") )


    def on_sendable ( self, event ) :
        while self.n_sent < self.n_messages :
            if event.sender.credit < 1 :
                break
            msg = Message ( body = self.n_sent )
            # Presettle the delivery.
            dlv = self.sender.send ( msg )
            dlv.settle()
            self.n_sent += 1


    def on_message ( self, event ) :
        self.n_received += 1
        if self.n_received >= self.n_messages :
            self.bail ( None )



class MulticastUnsettled ( MessagingHandler ) :
    def __init__ ( self,
                   addr,
                   n_messages,
                   n_receivers
                 ) :
        super ( MulticastUnsettled, self ) . __init__ ( prefetch = n_messages )
        self.addr        = addr
        self.n_messages  = n_messages
        self.n_receivers = n_receivers

        self.sender     = None
        self.receivers  = list ( )
        self.n_sent     = 0
        self.n_received = list ( )
        self.error      = None
        self.test_timer = None
        self.bailing    = False


    def run ( self ) :
        Container(self).run()


    def bail ( self, travail ) :
        self.bailing = True
        self.error = travail
        self.send_conn.close ( )
        self.recv_conn.close ( )
        self.test_timer.cancel ( )


    def timeout ( self, name ):
        self.bail ( "Timeout Expired" )


    def on_start ( self, event ):
        self.send_conn = event.container.connect ( self.addr )
        self.recv_conn = event.container.connect ( self.addr )

        self.sender = event.container.create_sender   ( self.send_conn, self.addr )
        for i in range ( self.n_receivers ) :
            rcvr = event.container.create_receiver ( self.send_conn, self.addr, name = "receiver_" + str(i) )
            self.receivers.append ( rcvr )
            rcvr.flow ( self.n_messages )
            self.n_received.append ( 0 )

        self.test_timer = event.reactor.schedule ( 15, MultiTimeout(self, "test") )


    def on_sendable ( self, event ) :
        while self.n_sent < self.n_messages :
            if event.sender.credit < 1 :
                break
            for i in range ( self.n_messages ) :
                msg = Message ( body = i )
                # The sender does not settle, but the 
                # receivers will..
                self.sender.send ( msg )
                self.n_sent += 1


    def on_message ( self, event ) :
        if self.bailing :
            return
        event.delivery.settle()
        for i in range ( self.n_receivers ) :
            if event.receiver == self.receivers [ i ] :
                # Body conetnts of the messages count from 0 ... n,
                # so the contents of this message should be same as
                # the current number of messages received by this receiver.
                if self.n_received [ i ] != event.message.body :
                    self.bail ( "out of order or missed message: receiver %d got %d instead of %d" %
                                ( i, event.message.body, self.n_received [ i ] )
                              )
                    return
                self.n_received [ i ] += 1
                self.check_n_received ( )


    def check_n_received ( self ) :
        for i in range ( self.n_receivers ) :
            if self.n_received [ i ] < self.n_messages :
                return
        # All messages have been received by all receivers.
        self.bail ( None )




class DispositionReturnsToClosedConnection ( MessagingHandler ) :

    def __init__ ( self,
                   addr,
                   n_messages
                 ) :
        super ( DispositionReturnsToClosedConnection, self ) . __init__ ( prefetch = n_messages )
        self.addr       = addr
        self.n_messages = n_messages

        self.n_sent     = 0
        self.n_received = 0


    def run ( self ) :
        Container(self).run()


    def bail ( self, travail ) :
        self.bailing = True
        self.test_timer.cancel ( )
        self.error = travail
        if self.send_conn :
            self.send_conn.close ( )
        self.recv_conn.close ( )


    def timeout ( self, name ) :
        self.bail ( "Timeout Expired" )


    def on_start ( self, event ):
        self.send_conn = event.container.connect ( self.addr )
        self.recv_conn = event.container.connect ( self.addr )
        self.sender   = event.container.create_sender   ( self.send_conn, self.addr )
        self.receiver = event.container.create_receiver ( self.recv_conn, self.addr )
        self.test_timer = event.reactor.schedule ( 15, MultiTimeout ( self, "test" ) )


    def on_sendable ( self, event ) :

        if not self.send_conn :
            return

        while self.n_sent < self.n_messages :
            if event.sender.credit < 1 :
                break
            msg = Message ( body = self.n_sent )
            self.sender.send ( msg )
            self.n_sent += 1

        # Immediately upon finishing sending all the messages, the 
        # sender closes its connection, so that when the dispositions
        # try to come back they will find no one who cares.
        # The only problem I can directly detect here is a test 
        # timeout. And, indirectly, we are making sure that the router
        # does not blow sky high.
        if self.n_sent >= self.n_messages :
            self.send_conn.close()
            self.send_conn = None


    # On the receiver side, we keep accepting and settling 
    # messages, tragically unaware that no one cares.
    def on_message ( self, event ) :
        event.delivery.update ( Delivery.ACCEPTED )
        event.delivery.settle ( )
        self.n_received += 1
        if self.n_received >= self.n_messages :
            self.bail ( None )





class SenderSettlesFirst ( MessagingHandler ) :
    def __init__ ( self,
                   addr,
                   n_messages
                 ) :
        super ( SenderSettlesFirst, self ) . __init__ ( prefetch = n_messages )
        self.addr        = addr
        self.n_messages  = n_messages

        self.test_timer = None
        self.sender     = None
        self.receiver   = None
        self.n_sent     = 0
        self.n_received = 0


    def run ( self ) :
        Container(self).run()


    def bail ( self, travail ) :
        self.bailing = True
        self.error = travail
        self.send_conn.close ( )
        self.recv_conn.close ( )
        self.test_timer.cancel ( )


    def timeout ( self, name ):
        self.bail ( "Timeout Expired" )


    def on_start ( self, event ):
        self.send_conn = event.container.connect ( self.addr )
        self.recv_conn = event.container.connect ( self.addr )

        self.sender      = event.container.create_sender   ( self.send_conn, self.addr )
        self.receiver    = event.container.create_receiver ( self.recv_conn, self.addr )
        self.test_timer  = event.reactor.schedule ( 15, MultiTimeout(self, "test") )


    def on_sendable ( self, event ) :
        while self.n_sent < self.n_messages :
            if event.sender.credit < 1 :
                break
            msg = Message ( body = self.n_sent )
            # Settle the delivery immediately after sending.
            dlv = self.sender.send ( msg )
            dlv.settle()
            self.n_sent += 1


    def on_message ( self, event ) :
        self.n_received += 1
        event.delivery.settle ( )
        if self.n_received >= self.n_messages :
            self.bail ( None )




class PropagatedDisposition ( MessagingHandler ) :
    def __init__ ( self,
                   addr,
                   n_messages
                 ) :
        super ( PropagatedDisposition, self ) . __init__ ( prefetch = n_messages )
        self.addr        = addr
        self.n_messages  = n_messages

        self.test_timer = None
        self.sender     = None
        self.receiver   = None
        self.n_sent     = 0
        self.n_received = 0
        self.n_accepted = 0
        self.bailing    = False


    def run ( self ) :
        Container(self).run()


    def bail ( self, travail ) :
        self.bailing = True
        self.error = travail
        self.send_conn.close ( )
        self.recv_conn.close ( )
        self.test_timer.cancel ( )


    def timeout ( self, name ):
        self.bail ( "Timeout Expired" )


    def on_start ( self, event ):
        self.send_conn = event.container.connect ( self.addr )
        self.recv_conn = event.container.connect ( self.addr )

        self.sender      = event.container.create_sender   ( self.send_conn, self.addr )
        self.receiver    = event.container.create_receiver ( self.recv_conn, self.addr )
        self.test_timer  = event.reactor.schedule ( 15, MultiTimeout(self, "test") )


    # Sender Side ================================================
    def on_sendable ( self, event ) :
        if self.bailing :
            return
        while self.n_sent < self.n_messages :
            if event.sender.credit < 1 :
                break
            msg = Message ( body = self.n_sent )
            dlv = self.sender.send ( msg )
            if dlv.remote_state != 0 :
                self.bail ( "remote state nonzero on send." )
                break
            if not dlv.pending :
                self.bail ( "dlv not pending immediately after send." )
                break

            self.n_sent += 1


    def on_accepted ( self, event ) :
        if self.bailing :
            return
        dlv = event.delivery
        if dlv.pending :
            self.bail ( "Delivery still pending after accepted." )
            return
        if dlv.remote_state != Delivery.ACCEPTED :
            self.bail ( "Delivery remote state is not ACCEPTED after accept." )
            return
        self.n_accepted += 1
        if self.n_accepted >= self.n_messages :
            # Success!
            self.bail ( None )


    # Receiver Side ================================================
    def on_message ( self, event ) :
        if self.bailing :
            return
        self.n_received += 1
        dlv = event.delivery
        if dlv.pending :
            self.bail ( 'Delivery still pending at receiver.' )
            return
        if dlv.local_state != 0 :
            self.bail ( 'At receiver: delivery local state nonzero at receiver before accept.' )
            return
        dlv.update ( Delivery.ACCEPTED )




class UsettledUndeliverable ( MessagingHandler ) :
    def __init__ ( self,
                   addr,
                   n_messages
                 ) :
        super ( UsettledUndeliverable, self ) . __init__ ( prefetch = n_messages )
        self.addr        = addr
        self.n_messages  = n_messages

        self.test_timer = None
        self.sender     = None
        self.n_sent     = 0
        self.n_received = 0
        self.bailing    = False


    def run ( self ) :
        Container(self).run()


    def bail ( self, travail ) :
        self.bailing = True
        self.error = travail
        self.send_conn.close ( )
        self.test_timer.cancel ( )


    def timeout ( self, name ):
        if self.n_sent > 0 :
            self.bail ( "Messages sent with no receiver." )
        else :
            self.bail ( None )


    def on_start ( self, event ):
        self.send_conn = event.container.connect ( self.addr )
        self.sender    = event.container.create_sender ( self.send_conn, self.addr )
        # Uh-oh. We are not creating a receiver! 
        self.test_timer = event.reactor.schedule ( 5, MultiTimeout(self, "test") )


    def on_sendable ( self, event ) :
        while self.n_sent < self.n_messages :
            msg = Message ( body = self.n_sent )
            dlv = self.sender.send ( msg )
            dlv.settle()
            self.n_sent += 1


    def on_message ( self, event ) :
        self.n_received += 1




class ThreeAck ( MessagingHandler ) :
    def __init__ ( self,
                   addr,
                   n_messages
                 ) :
        super ( ThreeAck, self ) . __init__ ( prefetch = n_messages )
        self.addr        = addr
        self.n_messages  = n_messages

        self.test_timer = None
        self.sender     = None
        self.receiver   = None
        self.n_sent     = 0
        self.n_received = 0
        self.n_accepted = 0
        self.bailing    = False
        self.tmp_dlv    = None


    def run ( self ) :
        Container(self).run()


    def bail ( self, travail ) :
        self.bailing = True
        self.error = travail
        self.send_conn.close ( )
        self.recv_conn.close ( )
        self.test_timer.cancel ( )


    def timeout ( self, name ):
        self.bail ( "Timeout Expired" )


    def on_start ( self, event ):
        self.send_conn = event.container.connect ( self.addr )
        self.recv_conn = event.container.connect ( self.addr )

        self.sender      = event.container.create_sender   ( self.send_conn, self.addr )
        self.receiver    = event.container.create_receiver ( self.recv_conn, self.addr )
        self.test_timer  = event.reactor.schedule ( 15, MultiTimeout(self, "test") )


    # Sender Side ================================================
    def on_sendable ( self, event ) :
        if self.bailing :
            return
        while self.n_sent < self.n_messages :
            if event.sender.credit < 1 :
                break
            msg = Message ( body = self.n_sent )
            dlv = self.sender.send ( msg )

            self.n_sent += 1


    def on_accepted ( self, event ) :
        if self.bailing :
            return
        dlv = event.delivery
        if dlv.remote_state != Delivery.ACCEPTED :
            self.bail ( "Delivery remote state is not ACCEPTED in on_accepted." )
            return
        # When sender knows that receiver has accepted, we settle.
        # That's two-ack.
        dlv.settle()
        self.n_accepted += 1
        if self.n_accepted >= self.n_messages :
            # Success!
            self.bail ( None )


    # Receiver Side ================================================
    def on_message ( self, event ) :
        if self.bailing :
            return
        dlv = event.delivery
        dlv.update ( Delivery.ACCEPTED )
        if event.message.body != self.n_received :
            self.bail ( "out-of-order message" )
            return
        self.n_received += 1
        if self.tmp_dlv == None :
            self.tmp_dlv = dlv

    # We have no way, on receiver side, of tracking when sender settles.
    # See PROTON-395 .




class MessageAnnotations ( MessagingHandler ) :
    def __init__ ( self,
                   addr,
                   n_messages
                 ) :
        super ( MessageAnnotations, self ) . __init__ ( prefetch = n_messages )
        self.addr        = addr
        self.n_messages  = n_messages

        self.test_timer = None
        self.sender     = None
        self.receiver   = None
        self.n_sent     = 0
        self.n_received = 0
        self.bailing    = False


    def run ( self ) :
        Container(self).run()


    def bail ( self, travail ) :
        self.bailing = True
        self.error = travail
        self.send_conn.close ( )
        self.recv_conn.close ( )
        self.test_timer.cancel ( )


    def timeout ( self, name ):
        self.bail ( "Timeout Expired" )


    def on_start ( self, event ):
        self.send_conn = event.container.connect ( self.addr )
        self.recv_conn = event.container.connect ( self.addr )

        self.sender      = event.container.create_sender   ( self.send_conn, self.addr )
        self.receiver    = event.container.create_receiver ( self.recv_conn, self.addr )
        self.test_timer  = event.reactor.schedule ( 15, MultiTimeout(self, "test") )


    def on_sendable ( self, event ) :

        if event.sender.credit < 1 :
            return
        # No added annotations.
        msg = Message ( body = self.n_sent )
        self.n_sent += 1
        self.sender.send ( msg )

        # Add an annotation.
        msg = Message ( body = self.n_sent )
        self.n_sent += 1
        msg.annotations = { 'x-opt-qd.ingress': 'i_changed_the_annotation' }
        self.sender.send ( msg )

        # Try to supply an invalid type for trace.
        msg = Message ( body = self.n_sent )
        self.n_sent += 1
        msg.annotations = { 'x-opt-qd.trace' : 45 }
        self.sender.send ( msg )

        # Add a value to the trace list.
        msg = Message ( body = self.n_sent )
        self.n_sent += 1
        msg.annotations = { 'x-opt-qd.trace' : [ '0/first-hop' ] }
        self.sender.send ( msg )


    def on_message ( self, event ) :
        ingress_router_name = '0/QDR'
        self.n_received += 1
        if self.n_received >= self.n_messages :
            self.bail ( None )
            return

        annotations = event.message.annotations

        if self.n_received == 1 :
            if annotations [ 'x-opt-qd.ingress' ] != ingress_router_name :
                self.bail ( 'Bad ingress router name on msg %d' % self.n_received )
                return
            if annotations [ 'x-opt-qd.trace' ] != [ ingress_router_name ] :
                self.bail ( 'Bad trace on msg %d.' % self.n_received )
                return

        elif self.n_received == 2 :
            if annotations [ 'x-opt-qd.ingress' ] != 'i_changed_the_annotation' :
                self.bail ( 'Bad ingress router name on msg %d' % self.n_received )
                return
            if annotations [ 'x-opt-qd.trace' ] != [ ingress_router_name ] :
                self.bail ( 'Bad trace on msg %d .' % self.n_received )
                return

        elif self.n_received == 3 :
            # The invalid type for trace has no effect.
            if annotations [ 'x-opt-qd.ingress' ] != ingress_router_name :
                self.bail ( 'Bad ingress router name on msg %d ' % self.n_received )
                return
            if annotations [ 'x-opt-qd.trace' ] != [ ingress_router_name ] :
                self.bail ( 'Bad trace on msg %d' % self.n_received )
                return

        elif self.n_received == 4 :
            if annotations [ 'x-opt-qd.ingress' ] != ingress_router_name :
                self.bail ( 'Bad ingress router name on msg %d ' % self.n_received )
                return
            # The sender prepended a value to the trace list.
            if annotations [ 'x-opt-qd.trace' ] != [ '0/first-hop', ingress_router_name ] :
                self.bail ( 'Bad trace on msg %d' % self.n_received )
                return
            # success
            self.bail ( None )




class StripMessageAnnotationsCustom ( MessagingHandler ) :
    def __init__ ( self,
                   addr,
                   n_messages
                 ) :
        super ( StripMessageAnnotationsCustom, self ) . __init__ ( prefetch = n_messages )
        self.addr        = addr
        self.n_messages  = n_messages

        self.test_timer  = None
        self.sender      = None
        self.receiver    = None
        self.n_sent      = 0
        self.n_received  = 0


    def run ( self ) :
        Container(self).run()


    def bail ( self, travail ) :
        self.bailing = True
        self.error = travail
        self.send_conn.close ( )
        self.recv_conn.close ( )
        self.test_timer.cancel ( )


    def timeout ( self, name ):
        self.bail ( "Timeout Expired" )


    def on_start ( self, event ):
        self.send_conn = event.container.connect ( self.addr )
        self.recv_conn = event.container.connect ( self.addr )

        self.sender      = event.container.create_sender   ( self.send_conn, self.addr )
        self.receiver    = event.container.create_receiver ( self.recv_conn, self.addr )
        self.test_timer  = event.reactor.schedule ( 15, MultiTimeout(self, "test") )


    def on_sendable ( self, event ) :
        while self.n_sent < self.n_messages :
            if event.sender.credit < 1 :
                break
            msg = Message ( body = self.n_sent )
            self.n_sent += 1
            msg.annotations = { 'custom-annotation' : '1/Custom_Annotation' }

            self.sender.send ( msg )


    def on_message ( self, event ) :
        self.n_received += 1
        if not 'custom-annotation' in event.message.annotations :
            self.bail ( 'custom annotation not found' )
            return
        if event.message.annotations [ 'custom-annotation'] != '1/Custom_Annotation' :
            self.bail ( 'custom annotation bad value' )
            return
        if self.n_received >= self.n_messages :
            # success
            self.bail ( None )



class StripMessageAnnotationsNo ( MessagingHandler ) :
    def __init__ ( self,
                   addr,
                   n_messages
                 ) :
        super ( StripMessageAnnotationsNo, self ) . __init__ ( prefetch = n_messages )
        self.addr        = addr
        self.n_messages  = n_messages

        self.test_timer  = None
        self.sender      = None
        self.receiver    = None
        self.n_sent      = 0
        self.n_received  = 0


    def run ( self ) :
        Container(self).run()


    def bail ( self, travail ) :
        self.bailing = True
        self.error = travail
        self.send_conn.close ( )
        self.recv_conn.close ( )
        self.test_timer.cancel ( )


    def timeout ( self, name ):
        self.bail ( "Timeout Expired" )


    def on_start ( self, event ):
        self.send_conn = event.container.connect ( self.addr )
        self.recv_conn = event.container.connect ( self.addr )

        self.sender      = event.container.create_sender   ( self.send_conn, self.addr )
        self.receiver    = event.container.create_receiver ( self.recv_conn, self.addr )
        self.test_timer  = event.reactor.schedule ( 15, MultiTimeout(self, "test") )


    def on_sendable ( self, event ) :
        while self.n_sent < self.n_messages :
            if event.sender.credit < 1 :
                break
            msg = Message ( body = self.n_sent )
            self.n_sent += 1
            # This test has no added annotations.
            # The receiver should get the expected standard annotations anyway,
            # because the address we are using has 'stripAnnotations' set to 'no'.
            msg.annotations = { }
            self.sender.send ( msg )


    def on_message ( self, event ) :
        self.n_received += 1

        if event.message.annotations [ 'x-opt-qd.ingress' ] != '0/QDR' :
            self.bail ( "x-opt-qd.ingress annotation has been stripped!" )
            return

        if event.message.annotations [ 'x-opt-qd.trace' ] != [ '0/QDR' ] :
            self.bail ( "x-opt-qd.trace annotations has been stripped!" )
            return

        if self.n_received >= self.n_messages :
            # success
            self.bail ( None )



class StripMessageAnnotationsNoAddTrace ( MessagingHandler ) :
    def __init__ ( self,
                   addr,
                   n_messages
                 ) :
        super ( StripMessageAnnotationsNoAddTrace, self ) . __init__ ( prefetch = n_messages )
        self.addr        = addr
        self.n_messages  = n_messages

        self.test_timer  = None
        self.sender      = None
        self.receiver    = None
        self.n_sent      = 0
        self.n_received  = 0


    def run ( self ) :
        Container(self).run()


    def bail ( self, travail ) :
        self.bailing = True
        self.error = travail
        self.send_conn.close ( )
        self.recv_conn.close ( )
        self.test_timer.cancel ( )


    def timeout ( self, name ):
        self.bail ( "Timeout Expired" )


    def on_start ( self, event ):
        self.send_conn = event.container.connect ( self.addr )
        self.recv_conn = event.container.connect ( self.addr )

        self.sender      = event.container.create_sender   ( self.send_conn, self.addr )
        self.receiver    = event.container.create_receiver ( self.recv_conn, self.addr )
        self.test_timer  = event.reactor.schedule ( 15, MultiTimeout(self, "test") )


    def on_sendable ( self, event ) :
        while self.n_sent < self.n_messages :
            if event.sender.credit < 1 :
                break
            msg = Message ( body = self.n_sent )
            annotations = {'Canis_meus' : 'id_comedit',
                           'x-opt-qd.ingress': 'ingress-router',
                           'x-opt-qd.trace': ['0/QDR.1']
            }
            self.n_sent += 1
            # This test has no added annotations.
            # The receiver should get the expected standard annotations anyway,
            # because the address we are using has 'stripAnnotations' set to 'no'.
            msg.annotations = annotations
            self.sender.send ( msg )


    def on_message ( self, event ) :
        self.n_received += 1

        notes = event.message.annotations

        if notes.__class__ != dict :
            self.bail ( "annotations are not a dictionary" )
            return
        # No annotations should get stripped -- neither the
        # ones that the router adds, not the custome one that
        # I added.
        if not 'x-opt-qd.ingress' in notes :
            self.bail ( 'x-opt-qd.ingress annotation missing' )
            return
        if not 'x-opt-qd.trace' in notes :
            self.bail ( 'x-opt-qd.trace annotation missing' )
            return
        if not 'Canis_meus' in notes :
            self.bail ( 'Canis_meus annotation missing' )
            return

        if notes [ 'x-opt-qd.ingress' ] != 'ingress-router' :
            self.bail ( "x-opt-qd.ingress bad value" )
            return
        if notes [ 'x-opt-qd.trace' ] != ['0/QDR.1', '0/QDR'] :
            self.bail ( "x-opt-qd.trace bad value" )
            return
        if notes [ 'Canis_meus' ] != 'id_comedit' :
            self.bail ( "Canis_meus bad value" )
            return

        if self.n_received >= self.n_messages :
            # success
            self.bail ( None )



class StripMessageAnnotationsBoth ( MessagingHandler ) :
    def __init__ ( self,
                   addr,
                   n_messages
                 ) :
        super ( StripMessageAnnotationsBoth, self ) . __init__ ( prefetch = n_messages )
        self.addr        = addr
        self.n_messages  = n_messages

        self.test_timer  = None
        self.sender      = None
        self.receiver    = None
        self.n_sent      = 0
        self.n_received  = 0


    def run ( self ) :
        Container(self).run()


    def bail ( self, travail ) :
        self.bailing = True
        self.error = travail
        self.send_conn.close ( )
        self.recv_conn.close ( )
        self.test_timer.cancel ( )


    def timeout ( self, name ):
        self.bail ( "Timeout Expired" )


    def on_start ( self, event ):
        self.send_conn = event.container.connect ( self.addr )
        self.recv_conn = event.container.connect ( self.addr )

        self.sender      = event.container.create_sender   ( self.send_conn, self.addr )
        self.receiver    = event.container.create_receiver ( self.recv_conn, self.addr )
        self.test_timer  = event.reactor.schedule ( 15, MultiTimeout(self, "test") )


    def on_sendable ( self, event ) :
        while self.n_sent < self.n_messages :
            if event.sender.credit < 1 :
                break
            msg = Message ( body = self.n_sent )
            annotations = { 'Canis_meus' : 'id_comedit',
                            'x-opt-qd.ingress': 'ingress-router',
                            'x-opt-qd.trace': ['0/QDR.1'],
                          }
            self.n_sent += 1
            # This test has no added annotations.
            # The receiver should get the expected standard annotations anyway,
            # because the address we are using has 'stripAnnotations' set to 'no'.
            msg.annotations = annotations
            self.sender.send ( msg )


    def on_message ( self, event ) :
        self.n_received += 1

        # The annotations that the router adds should get stripped,
        # but not the custom one that I added.
        notes = event.message.annotations
        if 'x-opt-qd.ingress' in notes :
            self.bail ( 'x-opt-qd.ingress annotation not stripped' )
            return
        if 'x-opt-qd.trace' in notes :
            self.bail ( 'x-opt-qd.trace annotation not stripped' )
            return
        if not 'Canis_meus' in notes :
            self.bail ( 'Canis_meus annotation missing' )
            return

        if notes [ 'Canis_meus' ] != 'id_comedit' :
            self.bail ( "Canis_meus bad value" )
            return

        if self.n_received >= self.n_messages :
            # success
            self.bail ( None )


class StripMessageAnnotationsOut ( MessagingHandler ) :
    def __init__ ( self,
                   addr,
                   n_messages
                 ) :
        super ( StripMessageAnnotationsOut, self ) . __init__ ( prefetch = n_messages )
        self.addr        = addr
        self.n_messages  = n_messages

        self.test_timer  = None
        self.sender      = None
        self.receiver    = None
        self.n_sent      = 0
        self.n_received  = 0


    def run ( self ) :
        Container(self).run()


    def bail ( self, travail ) :
        self.bailing = True
        self.error = travail
        self.send_conn.close ( )
        self.recv_conn.close ( )
        self.test_timer.cancel ( )


    def timeout ( self, name ):
        self.bail ( "Timeout Expired" )


    def on_start ( self, event ):
        self.send_conn = event.container.connect ( self.addr )
        self.recv_conn = event.container.connect ( self.addr )

        self.sender      = event.container.create_sender   ( self.send_conn, self.addr )
        self.receiver    = event.container.create_receiver ( self.recv_conn, self.addr )
        self.test_timer  = event.reactor.schedule ( 15, MultiTimeout(self, "test") )


    def on_sendable ( self, event ) :
        while self.n_sent < self.n_messages :
            if event.sender.credit < 1 :
                break
            msg = Message ( body = self.n_sent )
            self.n_sent += 1
            # This test has no added annotations.
            # The receiver should get the expected standard annotations anyway,
            # because the address we are using has 'stripAnnotations' set to 'no'.
            self.sender.send ( msg )


    def on_message ( self, event ) :
        self.n_received += 1

        # The annotations that the router routinely adds 
        # should all get stripped,
        if event.message.annotations != None :
            self.bail ( "An annotation was not stripped in egress message." )
            return

        if self.n_received >= self.n_messages :
            # success
            self.bail ( None )




class StripMessageAnnotationsIn ( MessagingHandler ) :
    def __init__ ( self,
                   addr,
                   n_messages
                 ) :
        super ( StripMessageAnnotationsIn, self ) . __init__ ( prefetch = n_messages )
        self.addr        = addr
        self.n_messages  = n_messages

        self.test_timer  = None
        self.sender      = None
        self.receiver    = None
        self.n_sent      = 0
        self.n_received  = 0


    def run ( self ) :
        Container(self).run()


    def bail ( self, travail ) :
        self.bailing = True
        self.error = travail
        self.send_conn.close ( )
        self.recv_conn.close ( )
        self.test_timer.cancel ( )


    def timeout ( self, name ):
        self.bail ( "Timeout Expired" )


    def on_start ( self, event ):
        self.send_conn = event.container.connect ( self.addr )
        self.recv_conn = event.container.connect ( self.addr )

        self.sender      = event.container.create_sender   ( self.send_conn, self.addr )
        self.receiver    = event.container.create_receiver ( self.recv_conn, self.addr )
        self.test_timer  = event.reactor.schedule ( 15, MultiTimeout(self, "test") )


    def on_sendable ( self, event ) :
        while self.n_sent < self.n_messages :
            if event.sender.credit < 1 :
                break
            msg = Message ( body = self.n_sent )
            # Attach some standard annotations to the message.
            # These are ingress annotations, and should get stripped.
            # These annotation-keys will then get values assigned by
            # the router.
            notes = {'x-opt-qd.ingress': 'ingress-router', 'x-opt-qd.trace': ['0/QDR.1']}
            self.sender.send ( msg )
            self.n_sent += 1


    def on_message ( self, event ) :
        self.n_received += 1

        if event.message.annotations [ 'x-opt-qd.ingress' ] == 'ingress-router' :
            self.bail ( "x-opt-qd.ingress value was not stripped." )
            return

        if event.message.annotations [ 'x-opt-qd.trace' ] == ['0/QDR.1'] :
            self.bail ( "x-opt-qd.trace value was not stripped." )
            return

        if self.n_received >= self.n_messages :
            # success
            self.bail ( None )






HELLO_WORLD = "Hello World!"

class SndSettleModeTest(MessagingHandler):
    def __init__(self, address):
        super(SndSettleModeTest, self).__init__()
        self.address = address
        self.sender = None
        self.receiver = None
        self.message_received = False
        self.delivery_already_settled = False

    def on_start(self, event):
        conn = event.container.connect(self.address)
        # The receiver sets link.snd_settle_mode = Link.SND_SETTLED. It wants to receive settled messages
        self.receiver = event.container.create_receiver(conn, "org/apache/dev", options=AtMostOnce())

        # With AtLeastOnce, the sender will not settle.
        self.sender = event.container.create_sender(conn, "org/apache/dev", options=AtLeastOnce())

    def on_sendable(self, event):
        msg = Message(body=HELLO_WORLD)
        event.sender.send(msg)
        event.sender.close()

    def on_message(self, event):
        self.delivery_already_settled = event.delivery.settled
        if HELLO_WORLD == event.message.body:
            self.message_received = True
        else:
            self.message_received = False
        event.connection.close()

    def run(self):
        Container(self).run()


class ExcessDeliveriesReleasedTest(MessagingHandler):
    def __init__(self, address):
        super(ExcessDeliveriesReleasedTest, self).__init__(prefetch=0)
        self.address = address
        self.dest = "closest.EDRtest"
        self.error = None
        self.sender = None
        self.receiver = None
        self.n_sent     = 0
        self.n_received = 0
        self.n_accepted = 0
        self.n_released = 0

    def on_start(self, event):
        conn = event.container.connect(self.address)
        self.sender   = event.container.create_sender(conn, self.dest)
        self.receiver = event.container.create_receiver(conn, self.dest)
        self.receiver.flow(6)

    def on_sendable(self, event):
        for i in range(10 - self.n_sent):
            msg = Message(body=i)
            event.sender.send(msg)
            self.n_sent += 1

    def on_accepted(self, event):
        self.n_accepted += 1

    def on_released(self, event):
        self.n_released += 1
        if self.n_released == 4:
            if self.n_accepted != 6:
                self.error = "Expected 6 accepted, got %d" % self.n_accepted
            if self.n_received != 6:
                self.error = "Expected 6 received, got %d" % self.n_received

            event.connection.close()

    def on_message(self, event):
        self.n_received += 1
        if self.n_received == 6:
            self.receiver.close()

    def run(self):
        Container(self).run()

class UnavailableBase(MessagingHandler):
    def __init__(self, address):
        super(UnavailableBase, self).__init__()
        self.address = address
        self.dest = "unavailable"
        self.conn = None
        self.sender = None
        self.receiver = None
        self.link_error = False
        self.link_closed = False
        self.passed = False
        self.timer = None
        self.link_name = "test_link"

    def check_if_done(self):
        if self.link_error and self.link_closed:
            self.passed = True
            self.conn.close()
            self.timer.cancel()

    def on_link_error(self, event):
        link = event.link
        if event.link.name == self.link_name and link.remote_condition.description \
                == "Node not found":
            self.link_error = True
        self.check_if_done()

    def on_link_remote_close(self, event):
        if event.link.name == self.link_name:
            self.link_closed = True
            self.check_if_done()

    def run(self):
        Container(self).run()

class UnavailableSender(UnavailableBase):
    def __init__(self, address):
        super(UnavailableSender, self).__init__(address)

    def on_start(self, event):
        self.timer = event.reactor.schedule(TIMEOUT, Timeout(self))
        self.conn = event.container.connect(self.address)
        # Creating a sender to an address with unavailable distribution
        # The router will not allow this link to be established. It will close the link with an error of
        # "Node not found"
        self.sender = event.container.create_sender(self.conn, self.dest, name=self.link_name)

class UnavailableReceiver(UnavailableBase):
    def __init__(self, address):
        super(UnavailableReceiver, self).__init__(address)

    def on_start(self, event):
        self.timer = event.reactor.schedule(TIMEOUT, Timeout(self))
        self.conn = event.container.connect(self.address)
        # Creating a receiver to an address with unavailable distribution
        # The router will not allow this link to be established. It will close the link with an error of
        # "Node not found"
        self.receiver = event.container.create_receiver(self.conn, self.dest, name=self.link_name)

class MulticastUnsettledTest(MessagingHandler):
    def __init__(self, address):
        super(MulticastUnsettledTest, self).__init__(prefetch=0)
        self.address = address
        self.dest = "multicast.MUtest"
        self.error = None
        self.count      = 10
        self.n_sent     = 0
        self.n_received = 0
        self.n_accepted = 0

    def check_if_done(self):
        if self.n_received == self.count * 2 and self.n_accepted == self.count:
            self.timer.cancel()
            self.conn.close()

    def timeout(self):
        self.error = "Timeout Expired: sent=%d, received=%d, accepted=%d" % (self.n_sent, self.n_received, self.n_accepted)
        self.conn.close()

    def on_start(self, event):
        self.timer     = event.reactor.schedule(TIMEOUT, Timeout(self))
        self.conn      = event.container.connect(self.address)
        self.sender    = event.container.create_sender(self.conn, self.dest)
        self.receiver1 = event.container.create_receiver(self.conn, self.dest, name="A")
        self.receiver2 = event.container.create_receiver(self.conn, self.dest, name="B")
        self.receiver1.flow(self.count)
        self.receiver2.flow(self.count)

    def on_sendable(self, event):
        for i in range(self.count - self.n_sent):
            msg = Message(body=i)
            event.sender.send(msg)
            self.n_sent += 1

    def on_accepted(self, event):
        self.n_accepted += 1
        self.check_if_done()

    def on_message(self, event):
        if not event.delivery.settled:
            self.error = "Received unsettled delivery"
        self.n_received += 1
        self.check_if_done()

    def run(self):
        Container(self).run()

class LargeMessageStreamTest(MessagingHandler):
    def __init__(self, address):
        super(LargeMessageStreamTest, self).__init__()
        self.address = address
        self.dest = "LargeMessageStreamTest"
        self.error = None
        self.count = 10
        self.n_sent = 0
        self.timer = None
        self.conn = None
        self.sender = None
        self.receiver = None
        self.n_received = 0
        self.body = ""
        for i in range(10000):
            self.body += "0123456789101112131415"

    def check_if_done(self):
        if self.n_received == self.count:
            self.timer.cancel()
            self.conn.close()

    def timeout(self):
        self.error = "Timeout Expired: sent=%d, received=%d" % (self.n_sent, self.n_received)
        self.conn.close()

    def on_start(self, event):
        self.timer = event.reactor.schedule(TIMEOUT, Timeout(self))
        self.conn = event.container.connect(self.address)
        self.sender = event.container.create_sender(self.conn, self.dest)
        self.receiver = event.container.create_receiver(self.conn, self.dest, name="A")
        self.receiver.flow(self.count)

    def on_sendable(self, event):
        for i in range(self.count):
            msg = Message(body=self.body)
            # send(msg) calls the stream function which streams data from sender to the router
            event.sender.send(msg)
            self.n_sent += 1

    def on_message(self, event):
        self.n_received += 1
        self.check_if_done()

    def run(self):
        Container(self).run()


class MultiframePresettledTest(MessagingHandler):
    def __init__(self, address):
        super(MultiframePresettledTest, self).__init__(prefetch=0)
        self.address = address
        self.dest = "closest.MFPtest"
        self.error = None
        self.count      = 10
        self.n_sent     = 0
        self.n_received = 0

        self.body = ""
        for i in range(10000):
            self.body += "0123456789"

    def check_if_done(self):
        if self.n_received == self.count:
            self.timer.cancel()
            self.conn.close()

    def timeout(self):
        self.error = "Timeout Expired: sent=%d, received=%d" % (self.n_sent, self.n_received)
        self.conn.close()

    def on_start(self, event):
        self.timer     = event.reactor.schedule(TIMEOUT, Timeout(self))
        self.conn      = event.container.connect(self.address)
        self.sender    = event.container.create_sender(self.conn, self.dest)
        self.receiver  = event.container.create_receiver(self.conn, self.dest, name="A")
        self.receiver.flow(self.count)

    def on_sendable(self, event):
        for i in range(self.count - self.n_sent):
            msg = Message(body=self.body)
            dlv = event.sender.send(msg)
            dlv.settle()
            self.n_sent += 1

    def on_message(self, event):
        if not event.delivery.settled:
            self.error = "Received unsettled delivery"
        self.n_received += 1
        self.check_if_done()

    def run(self):
        Container(self).run()

class MulticastUnsettledNoReceiverTest(MessagingHandler):
    """
    Creates a sender to a multicast address. Router provides a credit of 'linkCapacity' to this sender even
    if there are no receivers (The sender should be able to send messages to multicast addresses even when no receiver
    is connected). The router will send a disposition of released back to the sender and will end up dropping
    these messages since there is no receiver.
    """
    def __init__(self, address):
        super(MulticastUnsettledNoReceiverTest, self).__init__(prefetch=0)
        self.address = address
        self.dest = "multicast.MulticastNoReceiverTest"
        self.error = "Some error"
        self.n_sent = 0
        self.max_send = 250
        self.n_released = 0
        self.n_accepted = 0
        self.timer = None
        self.conn = None
        self.sender = None

    def check_if_done(self):
        if self.n_accepted > 0:
            self.error = "Messages should not be accepted as there are no receivers"
            self.timer.cancel()
            self.conn.close()
        elif self.n_sent == self.n_released:
            self.error = None

            if not self.error:
                local_node = Node.connect(self.address, timeout=TIMEOUT)
                for result in local_node.query(type='org.apache.qpid.dispatch.router.link').results:
                    if result[5] == 'in' and 'multicast.MulticastNoReceiverTest' in result[6]:
                        if result[16] != 250:
                            self.error = "Expected 250 dropped presettled deliveries but got " + str(result[16])
                        else:
                            outs = local_node.query(type='org.apache.qpid.dispatch.router')
                            pos = outs.attribute_names.index("droppedPresettledDeliveries")
                            results = outs.results[0]
                            if results[pos] != 250:
                                self.error = "When querying router, expected 250 dropped presettled " \
                                             "deliveries but got " + str(results[pos])
                            else:
                                pos = outs.attribute_names.index("releasedDeliveries")
                                if results[pos] < 250:
                                    self.error = "The number of released deliveries cannot be less that 250 " \
                                                 "but it is " + str(results[pos])

            self.timer.cancel()
            self.conn.close()

    def on_start(self, event):
        self.timer = event.reactor.schedule(TIMEOUT, Timeout(self))
        self.conn = event.container.connect(self.address)
        self.sender = event.container.create_sender(self.conn, self.dest)

    def on_sendable(self, event):
        if self.n_sent >= self.max_send:
            return
        self.n_sent += 1
        msg = Message(body=self.n_sent)
        event.sender.send(msg)

    def on_accepted(self, event):
        self.n_accepted += 1
        self.check_if_done()

    def on_released(self, event):
        self.n_released += 1
        self.check_if_done()

    def run(self):
        Container(self).run()


class ReleasedVsModifiedTest(MessagingHandler):
    def __init__(self, address):
        super(ReleasedVsModifiedTest, self).__init__(prefetch=0, auto_accept=False)
        self.address = address
        self.dest = "closest.RVMtest"
        self.error = None
        self.count      = 10
        self.accept     = 6
        self.n_sent     = 0
        self.n_received = 0
        self.n_released = 0
        self.n_modified = 0
        self.node_modified_at_start = 0

    def get_modified_deliveries ( self ) :
        local_node = Node.connect(self.address, timeout=TIMEOUT)
        outs = local_node.query(type='org.apache.qpid.dispatch.router')
        pos = outs.attribute_names.index("modifiedDeliveries")
        results = outs.results[0]
        n_modified_deliveries = results [ pos ]
        return n_modified_deliveries


    def check_if_done(self):
        if self.n_received == self.accept and self.n_released == self.count - self.accept and self.n_modified == self.accept:
            node_modified_now = self.get_modified_deliveries ( )
            this_test_modified_deliveries = node_modified_now - self.node_modified_at_start
            if this_test_modified_deliveries == self.accept:
                self.timer.cancel()
                self.conn.close()

    def timeout(self):
        self.error = "Timeout Expired: sent=%d, received=%d, released=%d, modified=%d" % \
                     (self.n_sent, self.n_received, self.n_released, self.n_modified)
        self.conn.close()

    def on_start(self, event):
        self.timer     = event.reactor.schedule(TIMEOUT, Timeout(self))
        self.conn      = event.container.connect(self.address)
        self.sender    = event.container.create_sender(self.conn, self.dest)
        self.receiver  = event.container.create_receiver(self.conn, self.dest, name="A")
        self.receiver.flow(self.accept)
        self.node_modified_at_start = self.get_modified_deliveries ( )

    def on_sendable(self, event):
        for i in range(self.count - self.n_sent):
            msg = Message(body="RvM-Test")
            event.sender.send(msg)
            self.n_sent += 1

    def on_message(self, event):
        self.n_received += 1
        if self.n_received == self.accept:
            self.receiver.close()

    def on_released(self, event):
        if event.delivery.remote_state == Delivery.MODIFIED:
            self.n_modified += 1
        else:
            self.n_released += 1
        self.check_if_done()

    def run(self):
        Container(self).run()


class AppearanceOfBalanceTest(MessagingHandler):
    def __init__(self, address):
        super(AppearanceOfBalanceTest, self).__init__()
        self.address = address
        self.dest = "balanced.AppearanceTest"
        self.error = None
        self.count        = 9
        self.n_sent       = 0
        self.n_received_a = 0
        self.n_received_b = 0
        self.n_received_c = 0

    def check_if_done(self):
        if self.n_received_a + self.n_received_b + self.n_received_c == self.count:
            if self.n_received_a != 3 or self.n_received_b != 3 or self.n_received_c != 3:
                self.error = "Incorrect Distribution: %d/%d/%d" % (self.n_received_a, self.n_received_b, self.n_received_c)
            self.timer.cancel()
            self.conn.close()

    def timeout(self):
        self.error = "Timeout Expired: sent=%d rcvd=%d/%d/%d" % \
                     (self.n_sent, self.n_received_a, self.n_received_b, self.n_received_c)
        self.conn.close()

    def on_start(self, event):
        self.timer      = event.reactor.schedule(TIMEOUT, Timeout(self))
        self.conn       = event.container.connect(self.address)
        self.sender     = event.container.create_sender(self.conn, self.dest)
        self.receiver_a = event.container.create_receiver(self.conn, self.dest, name="A")
        self.receiver_b = event.container.create_receiver(self.conn, self.dest, name="B")
        self.receiver_c = event.container.create_receiver(self.conn, self.dest, name="C")

    def send(self):
        if self.n_sent < self.count:
            msg = Message(body="Appearance-Test")
            self.sender.send(msg)
            self.n_sent += 1

    def on_sendable(self, event):
        if self.n_sent == 0:
            self.send()

    def on_message(self, event):
        if event.receiver == self.receiver_a:
            self.n_received_a += 1
        if event.receiver == self.receiver_b:
            self.n_received_b += 1
        if event.receiver == self.receiver_c:
            self.n_received_c += 1

    def on_accepted(self, event):
        self.send()
        self.check_if_done()

    def run(self):
        Container(self).run()


class BatchedSettlementTest(MessagingHandler):
    def __init__(self, address):
        super(BatchedSettlementTest, self).__init__(auto_accept=False)
        self.address = address
        self.dest = "balanced.BatchedSettlement"
        self.error = None
        self.count       = 200
        self.batch_count = 20
        self.n_sent      = 0
        self.n_received  = 0
        self.n_settled   = 0
        self.batch       = []
        self.accepted_count_match = False

    def check_if_done(self):
        if self.n_settled == self.count:
            local_node = Node.connect(self.address, timeout=TIMEOUT)
            outs = local_node.query(type='org.apache.qpid.dispatch.router')
            pos = outs.attribute_names.index("acceptedDeliveries")
            results = outs.results[0]
            if results[pos] >= self.count:
                self.accepted_count_match = True

            self.timer.cancel()
            self.conn.close()

    def timeout(self):
        self.error = "Timeout Expired: sent=%d rcvd=%d settled=%d" % \
                     (self.n_sent, self.n_received, self.n_settled)
        self.conn.close()

    def on_start(self, event):
        self.timer    = event.reactor.schedule(TIMEOUT, Timeout(self))
        self.conn     = event.container.connect(self.address)
        self.sender   = event.container.create_sender(self.conn, self.dest)
        self.receiver = event.container.create_receiver(self.conn, self.dest)

    def send(self):
        while self.n_sent < self.count and self.sender.credit > 0:
            msg = Message(body="Batch-Test")
            self.sender.send(msg)
            self.n_sent += 1

    def on_sendable(self, event):
        self.send()

    def on_message(self, event):
        self.n_received += 1
        self.batch.insert(0, event.delivery)
        if len(self.batch) == self.batch_count:
            while len(self.batch) > 0:
                self.accept(self.batch.pop())

    def on_accepted(self, event):
        self.n_settled += 1
        self.check_if_done()

    def run(self):
        Container(self).run()


class RejectCoordinatorTest(MessagingHandler, TransactionHandler):
    def __init__(self, url):
        super(RejectCoordinatorTest, self).__init__(prefetch=0)
        self.url = Url(url)
        self.error = "The router can't coordinate transactions by itself, a linkRoute to a coordinator must be " \
                     "configured to use transactions."
        self.container = None
        self.conn = None
        self.sender = None
        self.timer = None
        self.passed = False
        self.link_error = False
        self.link_remote_close = False

    def timeout(self):
        self.conn.close()

    def check_if_done(self):
        if self.link_remote_close and self.link_error:
            self.passed = True
            self.conn.close()
            self.timer.cancel()

    def on_start(self, event):
        self.timer = event.reactor.schedule(TIMEOUT, Timeout(self))
        self.container = event.container
        self.conn = self.container.connect(self.url)
        self.sender = self.container.create_sender(self.conn, self.url.path)
        # declare_transaction tries to create a link with name "txn-ctrl" to the
        # transaction coordinator which has its own target, it has no address
        # The router cannot coordinate transactions itself and so there will be a link error when this
        # link is attempted to be created
        self.container.declare_transaction(self.conn, handler=self)

    def on_link_error(self, event):
        link = event.link
        # If the link name is 'txn-ctrl' and there is a link error and it matches self.error, then we know
        # that the router has rejected the link because it cannot coordinate transactions itself
        if link.name == "txn-ctrl" and link.remote_condition.description == self.error and \
                        link.remote_condition.name == 'amqp:precondition-failed':
            self.link_error = True
            self.check_if_done()

    def on_link_remote_close(self, event):
        link = event.link
        if link.name == "txn-ctrl":
            self.link_remote_close = True
            self.check_if_done()

    def run(self):
        Container(self).run()




class PresettledOverflowTest(MessagingHandler):
    def __init__(self, address):
        super(PresettledOverflowTest, self).__init__(prefetch=0)
        self.address = address
        self.dest = "balanced.PresettledOverflow"
        self.error = None
        self.count       = 500
        self.n_sent      = 0
        self.n_received  = 0
        self.last_seq    = -1

    def timeout(self):
        self.error = "Timeout Expired: sent=%d rcvd=%d last_seq=%d" % (self.n_sent, self.n_received, self.last_seq)
        self.conn.close()

    def on_start(self, event):
        self.timer    = event.reactor.schedule(TIMEOUT, Timeout(self))
        self.conn     = event.container.connect(self.address)
        self.sender   = event.container.create_sender(self.conn, self.dest)
        self.receiver = event.container.create_receiver(self.conn, self.dest)
        self.receiver.flow(10)

    def send(self):
        while self.n_sent < self.count and self.sender.credit > 0:
            msg = Message(body={"seq": self.n_sent})
            dlv = self.sender.send(msg)
            dlv.settle()
            self.n_sent += 1
        if self.n_sent == self.count:
            self.receiver.flow(self.count)

    def on_sendable(self, event):
        if self.n_sent < self.count:
            self.send()

    def on_message(self, event):
        self.n_received += 1
        self.last_seq = event.message.body["seq"]
        if self.last_seq == self.count - 1:
            if self.n_received == self.count:
                self.error = "No deliveries were dropped"

            if not self.error:
                local_node = Node.connect(self.address, timeout=TIMEOUT)
                out = local_node.query(type='org.apache.qpid.dispatch.router.link')

                for result in out.results:
                    if result[5] == 'out' and 'balanced.PresettledOverflow' in result[6]:
                        if result[16] != 250:
                            self.error = "Expected 250 dropped presettled deliveries but got " + str(result[16])
                        else:
                            outs = local_node.query(type='org.apache.qpid.dispatch.router')
                            pos_presett = outs.attribute_names.index("presettledDeliveries")
                            pos = outs.attribute_names.index("droppedPresettledDeliveries")
                            results = outs.results[0]
                            # Enforce presettledDeliveries metric is updated
                            if results[pos_presett] < 500:
                                self.error = "When querying router, expected 500 presettled " \
                                             "deliveries but got " + str(results[pos_presett])
                            # There is 250 from a previous test
                            if results[pos] < 500:
                                self.error = "When querying router, expected 500 dropped presettled " \
                                             "deliveries but got " + str(results[pos])
            self.conn.close()
            self.timer.cancel()

    def run(self):
        Container(self).run()


class RejectDispositionTest(MessagingHandler):
    def __init__(self, address):
        super(RejectDispositionTest, self).__init__(auto_accept=False)
        self.address = address
        self.sent = False
        self.received_error = False
        self.dest = "rejectDispositionTest"
        # explicitly convert to str due to
        # https://issues.apache.org/jira/browse/PROTON-1843
        self.error_description = str('you were out of luck this time!')
        self.error_name = u'amqp:internal-error'
        self.reject_count_match = False
        self.rejects_at_start = 0

    def count_rejects ( self ) :
        local_node = Node.connect(self.address, timeout=TIMEOUT)
        outs = local_node.query(type='org.apache.qpid.dispatch.router')
        pos = outs.attribute_names.index("rejectedDeliveries")
        results = outs.results[0]
        return results[pos]

    def on_start(self, event):
        conn = event.container.connect(self.address)
        event.container.create_sender(conn, self.dest)
        event.container.create_receiver(conn, self.dest)
        self.rejects_at_start = self.count_rejects ( )

    def on_sendable(self, event):
        if not self.sent:
            event.sender.send(Message(body=u"Hello World!"))
            self.sent = True

    def on_rejected(self, event):
        if event.delivery.remote.condition.description == self.error_description \
                and event.delivery.remote.condition.name == self.error_name:
            self.received_error = True
        rejects_now = self.count_rejects ( )
        rejects_for_this_test = rejects_now - self.rejects_at_start
        if rejects_for_this_test == 1:
            self.reject_count_match = True
        event.connection.close()

    def on_message(self, event):
        event.delivery.local.condition = Condition(self.error_name, self.error_description)
        self.reject(event.delivery)

    def run(self):
        Container(self).run()


if __name__ == '__main__':
    unittest.main(main_module())
