# Copyright 2013 IBM Corp.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_config import cfg
from oslotest import mockpatch
import testtools

from tempest import config
from tempest import exceptions
from tempest.lib.common.utils import data_utils
from tempest import test
from tempest.tests import base
from tempest.tests import fake_config


class BaseDecoratorsTest(base.TestCase):
    def setUp(self):
        super(BaseDecoratorsTest, self).setUp()
        self.config_fixture = self.useFixture(fake_config.ConfigFixture())
        self.patchobject(config, 'TempestConfigPrivate',
                         fake_config.FakePrivate)


class TestAttrDecorator(BaseDecoratorsTest):
    def _test_attr_helper(self, expected_attrs, **decorator_args):
        @test.attr(**decorator_args)
        def foo():
            pass

        # By our test.attr decorator the attribute __testtools_attrs will be
        # set only for 'type' argument, so we test it first.
        if 'type' in decorator_args:
            # this is what testtools sets
            self.assertEqual(getattr(foo, '__testtools_attrs'),
                             set(expected_attrs))

    def test_attr_without_type(self):
        self._test_attr_helper(expected_attrs='baz', bar='baz')

    def test_attr_decorator_with_list_type(self):
        # if type is 'smoke' we'll get the original list of types
        self._test_attr_helper(expected_attrs=['smoke', 'foo'],
                               type=['smoke', 'foo'])

    def test_attr_decorator_with_unknown_type(self):
        self._test_attr_helper(expected_attrs=['foo'], type='foo')

    def test_attr_decorator_with_duplicated_type(self):
        self._test_attr_helper(expected_attrs=['foo'], type=['foo', 'foo'])


class TestIdempotentIdDecorator(BaseDecoratorsTest):

    def _test_helper(self, _id, **decorator_args):
        @test.idempotent_id(_id)
        def foo():
            """Docstring"""
            pass

        return foo

    def _test_helper_without_doc(self, _id, **decorator_args):
        @test.idempotent_id(_id)
        def foo():
            pass

        return foo

    def test_positive(self):
        _id = data_utils.rand_uuid()
        foo = self._test_helper(_id)
        self.assertIn('id-%s' % _id, getattr(foo, '__testtools_attrs'))
        self.assertTrue(foo.__doc__.startswith('Test idempotent id: %s' % _id))

    def test_positive_without_doc(self):
        _id = data_utils.rand_uuid()
        foo = self._test_helper_without_doc(_id)
        self.assertTrue(foo.__doc__.startswith('Test idempotent id: %s' % _id))

    def test_idempotent_id_not_str(self):
        _id = 42
        self.assertRaises(TypeError, self._test_helper, _id)

    def test_idempotent_id_not_valid_uuid(self):
        _id = '42'
        self.assertRaises(ValueError, self._test_helper, _id)


class TestServicesDecorator(BaseDecoratorsTest):
    def _test_services_helper(self, *decorator_args):
        class TestFoo(test.BaseTestCase):
            @test.services(*decorator_args)
            def test_bar(self):
                return 0

        t = TestFoo('test_bar')
        self.assertEqual(set(decorator_args), getattr(t.test_bar,
                                                      '__testtools_attrs'))
        self.assertEqual(t.test_bar(), 0)

    def test_services_decorator_with_single_service(self):
        self._test_services_helper('compute')

    def test_services_decorator_with_multiple_services(self):
        self._test_services_helper('compute', 'network')

    def test_services_decorator_with_duplicated_service(self):
        self._test_services_helper('compute', 'compute')

    def test_services_decorator_with_invalid_service(self):
        self.assertRaises(exceptions.InvalidServiceTag,
                          self._test_services_helper, 'compute',
                          'bad_service')

    def test_services_decorator_with_service_valid_and_unavailable(self):
        self.useFixture(mockpatch.PatchObject(test.CONF.service_available,
                                              'cinder', False))
        self.assertRaises(testtools.TestCase.skipException,
                          self._test_services_helper, 'compute',
                          'volume')

    def test_services_list(self):
        service_list = test.get_service_list()
        for service in service_list:
            try:
                self._test_services_helper(service)
            except exceptions.InvalidServiceTag:
                self.fail('%s is not listed in the valid service tag list'
                          % service)
            except KeyError:
                # NOTE(mtreinish): This condition is to test for an entry in
                # the outer decorator list but not in the service_list dict.
                # However, because we're looping over the service_list dict
                # it's unlikely we'll trigger this. So manual review is still
                # need for the list in the outer decorator.
                self.fail('%s is in the list of valid service tags but there '
                          'is no corresponding entry in the dict returned from'
                          ' get_service_list()' % service)
            except testtools.TestCase.skipException:
                # Test didn't raise an exception because of an incorrect list
                # entry so move onto the next entry
                continue


class TestStressDecorator(BaseDecoratorsTest):
    def _test_stresstest_helper(self, expected_frequency='process',
                                expected_inheritance=False,
                                **decorator_args):
        @test.stresstest(**decorator_args)
        def foo():
            pass
        self.assertEqual(getattr(foo, 'st_class_setup_per'),
                         expected_frequency)
        self.assertEqual(getattr(foo, 'st_allow_inheritance'),
                         expected_inheritance)
        self.assertEqual(set(['stress']), getattr(foo, '__testtools_attrs'))

    def test_stresstest_decorator_default(self):
        self._test_stresstest_helper()

    def test_stresstest_decorator_class_setup_frequency(self):
        self._test_stresstest_helper('process', class_setup_per='process')

    def test_stresstest_decorator_class_setup_frequency_non_default(self):
        self._test_stresstest_helper(expected_frequency='application',
                                     class_setup_per='application')

    def test_stresstest_decorator_set_frequency_and_inheritance(self):
        self._test_stresstest_helper(expected_frequency='application',
                                     expected_inheritance=True,
                                     class_setup_per='application',
                                     allow_inheritance=True)


class TestRequiresExtDecorator(BaseDecoratorsTest):
    def setUp(self):
        super(TestRequiresExtDecorator, self).setUp()
        cfg.CONF.set_default('api_extensions', ['enabled_ext', 'another_ext'],
                             'compute-feature-enabled')

    def _test_requires_ext_helper(self, expected_to_skip=True,
                                  **decorator_args):
        class TestFoo(test.BaseTestCase):
            @test.requires_ext(**decorator_args)
            def test_bar(self):
                return 0

        t = TestFoo('test_bar')
        if expected_to_skip:
            self.assertRaises(testtools.TestCase.skipException, t.test_bar)
        else:
            try:
                self.assertEqual(t.test_bar(), 0)
            except testtools.TestCase.skipException:
                # We caught a skipException but we didn't expect to skip
                # this test so raise a hard test failure instead.
                raise testtools.TestCase.failureException(
                    "Not supposed to skip")

    def test_requires_ext_decorator(self):
        self._test_requires_ext_helper(expected_to_skip=False,
                                       extension='enabled_ext',
                                       service='compute')

    def test_requires_ext_decorator_disabled_ext(self):
        self._test_requires_ext_helper(extension='disabled_ext',
                                       service='compute')

    def test_requires_ext_decorator_with_all_ext_enabled(self):
        cfg.CONF.set_default('api_extensions', ['all'],
                             group='compute-feature-enabled')
        self._test_requires_ext_helper(expected_to_skip=False,
                                       extension='random_ext',
                                       service='compute')

    def test_requires_ext_decorator_bad_service(self):
        self.assertRaises(KeyError,
                          self._test_requires_ext_helper,
                          extension='enabled_ext',
                          service='bad_service')


class TestConfigDecorators(BaseDecoratorsTest):
    def setUp(self):
        super(TestConfigDecorators, self).setUp()
        cfg.CONF.set_default('nova', True, 'service_available')
        cfg.CONF.set_default('glance', False, 'service_available')

    def _assert_skip_message(self, func, skip_msg):
        try:
            func()
            self.fail()
        except testtools.TestCase.skipException as skip_exc:
            self.assertEqual(skip_exc.args[0], skip_msg)

    def _test_skip_unless_config(self, expected_to_skip=True, *decorator_args):

        class TestFoo(test.BaseTestCase):
            @config.skip_unless_config(*decorator_args)
            def test_bar(self):
                return 0

        t = TestFoo('test_bar')
        if expected_to_skip:
            self.assertRaises(testtools.TestCase.skipException, t.test_bar)
            if (len(decorator_args) >= 3):
                # decorator_args[2]: skip message specified
                self._assert_skip_message(t.test_bar, decorator_args[2])
        else:
            try:
                self.assertEqual(t.test_bar(), 0)
            except testtools.TestCase.skipException:
                # We caught a skipException but we didn't expect to skip
                # this test so raise a hard test failure instead.
                raise testtools.TestCase.failureException(
                    "Not supposed to skip")

    def _test_skip_if_config(self, expected_to_skip=True,
                             *decorator_args):

        class TestFoo(test.BaseTestCase):
            @config.skip_if_config(*decorator_args)
            def test_bar(self):
                return 0

        t = TestFoo('test_bar')
        if expected_to_skip:
            self.assertRaises(testtools.TestCase.skipException, t.test_bar)
            if (len(decorator_args) >= 3):
                # decorator_args[2]: skip message specified
                self._assert_skip_message(t.test_bar, decorator_args[2])
        else:
            try:
                self.assertEqual(t.test_bar(), 0)
            except testtools.TestCase.skipException:
                # We caught a skipException but we didn't expect to skip
                # this test so raise a hard test failure instead.
                raise testtools.TestCase.failureException(
                    "Not supposed to skip")

    def test_skip_unless_no_group(self):
        self._test_skip_unless_config(True, 'fake_group', 'an_option')

    def test_skip_unless_no_option(self):
        self._test_skip_unless_config(True, 'service_available',
                                      'not_an_option')

    def test_skip_unless_false_option(self):
        self._test_skip_unless_config(True, 'service_available', 'glance')

    def test_skip_unless_false_option_msg(self):
        self._test_skip_unless_config(True, 'service_available', 'glance',
                                      'skip message')

    def test_skip_unless_true_option(self):
        self._test_skip_unless_config(False,
                                      'service_available', 'nova')

    def test_skip_if_no_group(self):
        self._test_skip_if_config(False, 'fake_group', 'an_option')

    def test_skip_if_no_option(self):
        self._test_skip_if_config(False, 'service_available', 'not_an_option')

    def test_skip_if_false_option(self):
        self._test_skip_if_config(False, 'service_available', 'glance')

    def test_skip_if_true_option(self):
        self._test_skip_if_config(True, 'service_available', 'nova')

    def test_skip_if_true_option_msg(self):
        self._test_skip_if_config(True, 'service_available', 'nova',
                                  'skip message')
