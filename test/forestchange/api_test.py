# Global Forest Watch API
# Copyright (C) 2014 World Resource Institute
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""Unit test coverage for the gfw.forestchange.api module.

These test the actual RequestHandlers in the api module for both analysis
and download queries. This doesn't test the CartoDB SQL used. See the
test/gfw.forestchange.sql for that.
"""

import itertools
import requests
import unittest
import webapp2
import webtest

from contextlib import closing

from google.appengine.ext import testbed

from gfw.forestchange import args, sql
from gfw.forestchange import api
from gfw import common


def combos(params, repeat=None, min=None):
    """Returns a sequence of param tuples (name, value)."""
    result = set()
    if not repeat:
        repeat = len(params) + 1
    if not min:
        min = 1
    for x in range(min, repeat):
        result.update(itertools.combinations(params, x))
    result = list(result)
    result.append(())
    return result


class BaseTest(unittest.TestCase):

    def setUp(self):
        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_datastore_v3_stub()
        self.testbed.init_memcache_stub()
        self.testbed.init_mail_stub()
        self.testbed.init_urlfetch_stub()
        self.mail_stub = self.testbed.get_stub(testbed.MAIL_SERVICE_NAME)

        app = webapp2.WSGIApplication([(r'/forest-change.*', api.Handler)])
        self.testapp = webtest.TestApp(app)

        self.content_types = dict(
            csv='text/csv',
            kml='application/kml',
            geojson='application/json',
            svg='image/svg+xml',
            shp='application/zip'
        )

    def tearDown(self):
        self.testbed.deactivate()

    def fetch(self, url, fmt):
        with closing(requests.get(url, stream=True)) as r:
            return r

    def download_helper(self, path, args={}):
        """Test download for supplied path and args."""
        for fmt in ['csv', 'geojson', 'kml', 'shp', 'svg']:
            args['download'] = 'file.%s' % fmt
            r = self.testapp.get(path, args)
            self.assertEqual(302, r.status_code)
            self.assertIn('location', r.headers)
            self.assertIn('http://wri-01.cartodb.com', r.headers['location'])
            response = self.fetch(r.headers['location'], fmt)
            if response.status_code != 200:
                print '\nERROR - %s\n%s\n%s\n%s\n' % \
                    (path, args, response.json(), r.headers['location'])
            else:
                self.assertIn(
                    self.content_types[fmt], response.headers['Content-Type'])


class FunctionTest(unittest.TestCase):

    """Test for the FormaIsoHandler."""

    def setUp(self):
        self.args = [
            ('bust', 1),
            ('period', '2008-01-01,2009-01-01')]

    def test_dataset_from_path(self):
        path = '/forest-change/forma-alerts/admin/bra'
        dataset = api._dataset_from_path(path)

        self.assertEqual('forma-alerts', dataset)

        path = '/forest-change/forma-alerts'
        dataset = api._dataset_from_path(path)

    def test_classify_request(self):
        path = '/forest-change/forma-alerts'
        self.assertEqual(('forma-alerts', 'all'), api._classify_request(path))

        path = '/forest-change/forma-alerts/admin/bra'
        self.assertEqual(('forma-alerts', 'iso'), api._classify_request(path))

        path = '/forest-change/forma-alerts/admin/bra/123'
        self.assertEqual(('forma-alerts', 'id1'), api._classify_request(path))

        path = '/forest-change/forma-alerts/wdpa/123'
        self.assertEqual(('forma-alerts', 'wdpa'), api._classify_request(path))


class UmdTest(BaseTest):

    """Test for UMD requests."""

    def setUp(self):
        super(UmdTest, self).setUp()
        self.args = [
            ('bust', 1),
            ('dev', 1),
            ('thresh', 10)]

    def testGetNational(self):
        path = r'/forest-change/umd-loss-gain/admin/bra'

        for thresh in [10, 15, 20, 25, 30, 50, 75]:
            for combo in combos(self.args):
                args = dict(combo)
                args['thresh'] = thresh
                print '%s %s' % (path, args)
                r = self.testapp.get(path, args)
                self.assertIn('years', r.json)
                self.assertEqual(len(r.json['years']), 13)
                self.assertIn('params', r.json)
                self.assertIn('iso', r.json['params'])
                self.assertEqual(r.json['params']['iso'], 'bra')
                self.assertEqual(200, r.status_code)

    def testGetSubnational(self):
        path = r'/forest-change/umd-loss-gain/admin/bra/2'

        for thresh in [10, 15, 20, 25, 30, 50, 75]:
            for combo in combos(self.args):
                args = dict(combo)
                args['thresh'] = thresh
                print '%s %s' % (path, args)
                r = self.testapp.get(path, args)
                self.assertIn('years', r.json)
                self.assertEqual(len(r.json['years']), 13)
                self.assertIn('params', r.json)
                self.assertIn('iso', r.json['params'])
                self.assertEqual(r.json['params']['iso'], 'bra')
                self.assertIn('id1', r.json['params'])
                self.assertEqual(r.json['params']['id1'], '2')
                self.assertEqual(200, r.status_code)


class FormaTest(BaseTest):

    """Test for FORMA requests."""

    def setUp(self):
        super(FormaTest, self).setUp()
        self.args = [
            ('bust', 1),
            ('dev', 1),
            ('period', '2008-01-01,2014-01-01')]

    def testGetNational(self):
        path = r'/forest-change/forma-alerts/admin/bra'

        for combo in combos(self.args):
            args = dict(combo)
            print '%s %s' % (path, args)
            r = self.testapp.get(path, args)
            self.assertIn('value', r.json)
            self.assertIn('params', r.json)
            self.assertIn('iso', r.json['params'])
            self.assertEqual(200, r.status_code)
            # self.download_helper(path, args)

    def testGetSubnational(self):
        path = r'/forest-change/forma-alerts/admin/bra/2'

        for combo in combos(self.args):
            args = dict(combo)
            print '%s %s' % (path, args)
            r = self.testapp.get(path, args)
            self.assertIn('value', r.json)
            self.assertIn('params', r.json)
            self.assertIn('iso', r.json['params'])
            self.assertEqual(r.json['params']['iso'], 'bra')
            self.assertIn('id1', r.json['params'])
            self.assertEqual(r.json['params']['id1'], '2')
            self.assertEqual(200, r.status_code)
            # self.download_helper(path, args)


if __name__ == '__main__':
    reload(common)
    reload(api)
    reload(args)
    reload(sql)
    unittest.main(exit=False, failfast=True)