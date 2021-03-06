"""Python client for Freckle"""
from cStringIO import StringIO
import datetime
import json
import urllib

import httplib2
import iso8601
import yaml
# Ugh, this is sad...
ETREE_MODULES = [
    'lxml.etree',
    'xml.etree.cElementTree',
    'cElementTree',
    'xml.etree.ElementTree',
    'elementtree.ElementTree',
]
etree = None
for name in ETREE_MODULES:
    try:
        etree = __import__(name, '', '', [''])
        break
    except ImportError:
        continue
if etree is None:
    raise ImportError("Failed to import ElementTree from any known place")



class Freckle(object):
    """Class for interacting with the Freckle API"""

    def __init__(self, account, token):
        self.endpoint = "https://%s.letsfreckle.com/api" % account
        self.headers = {"X-FreckleToken":token}
        self.http = httplib2.Http()

    def request(self, url, method="GET", body="", request_type="xml"):
        """Make a request to Freckle and return Python objects"""
        resp, content = self.http.request(url, method, body,
            headers=self.headers)
        if request_type == "xml":
            return self.parse_response(content)
        return self.parse_json_response(content)

    def paginated_request(self, url, method="GET", body="", page=1,
                          request_type="xml"):
        # This was added to help with paginated responses in freckle's API
        url = "%s&page=%s&per_page=100" % (url, page)
        """Make a request to Freckle and return Python objects"""
        resp, content = self.http.request(
            url, method, body, headers=self.headers)
        # if resp['link'] contains rel="next" at this point,
        # then there are more entries after this page.
        more_pages = False
        if resp.has_key('link') and "next" in resp['link']:
            more_pages = True
        if request_type == "xml":
            return self.parse_response(content), more_pages
        return self.parse_json_response(content), more_pages

    def get_entries(self, request_type="xml", **kwargs):
        """
        Get time entries from Freckle

        Optional search arguments:

           * people: a list of user ids
           * projects: a list of project ids
           * tags: a list of tag ids and/or names
           * date_to: a `datetime.date` object
           * date_from: a `datetime.date` object
           * billable: a boolean
        """
        search_args = {}
        for search in ('people', 'projects', 'tags'):
            if search in kwargs:
                as_string = ",".join([str(i) for i in kwargs[search]])
                search_args['search[%s]' % search] = as_string
        for search in ('date_to', 'date_from'):
            if search in kwargs:
                date = kwargs[search].strftime("%Y-%m-%d")
                # strip "date_"
                freckle_keyword = 'search[%s]' % search[5:]
                search_args[freckle_keyword] = date
        if "billable" in kwargs:
            if kwargs['billable']:
                val = "true"
            else:
                val = "false"
            search_args['search[billable]'] = val
        query = urllib.urlencode(search_args)

        # entries may be paginated, we need to make sure we get all of them
        more_pages = True
        page = 1
        entries = []
        while more_pages:
            entry_data, more_pages = self.paginated_request(
                "%s/entries.%s?%s" % (self.endpoint, request_type, query),
                page=page, request_type=request_type
            )
            entries.extend(entry_data)
            page += 1
        return entries

    def get_users(self, request_type="xml"):
        """Get users from Freckle"""
        return self.request(
            "%s/users.%s" % (self.endpoint, request_type),
            request_type=request_type
        )

    def get_projects(self, request_type="xml"):
        """Get projects from Freckle"""
        return self.request(
            "%s/projects.%s" % (self.endpoint, request_type),
            request_type=request_type
        )

    def parse_response(self, xml_content):
        """Parse XML response into Python"""
        content = []
        tree = etree.parse(StringIO(xml_content))
        for elem in tree.getroot().getchildren():
            as_dict = {}
            for item in elem.getchildren():
                if item.get("type") and item.text:
                    parser = "%s_as_python" % item.get("type")
                    try:
                        as_python = getattr(self, parser)(item.text)
                    except yaml.scanner.ScannerError:
                        pass
                elif item.get("type"):
                    as_python = None
                else:
                    as_python = item.text
                as_dict[item.tag] = as_python
            content.append(as_dict)
        return content

    def parse_json_response(self, json_content):
        """Parse JSON response into Python"""
        return json.loads(json_content)

    def boolean_as_python(self, val):
        """Convert text to boolean"""
        if val == 'true':
            return True
        else:
            return False

    def date_as_python(self, val):
        """Convert text to date"""
        return datetime.date(*[int(x) for x in val.split("-")])

    def datetime_as_python(self, val):
        """Convert text to datetime"""
        return iso8601.parse_date(val)

    def integer_as_python(self, val):
        """Convert text to integer"""
        return int(val)

    def array_as_python(self, val):
        """Convert text to list"""
        return val.split(",")

    def yaml_as_python(self, val):
        """Convert YAML to dict"""
        return yaml.load(val)