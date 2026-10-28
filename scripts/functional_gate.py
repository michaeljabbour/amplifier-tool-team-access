#!/usr/bin/env python3
"""Source-specific acceptance without providers, invitations or filming."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

from addteam.config import _parse_yaml_config
class Gate(unittest.TestCase):
    def test_fictional_roles_preserve_declared_permissions(self):
        with patch('addteam.config._git_root',return_value=None):
            c=_parse_yaml_config('admins:\n  - example-admin\nreaders:\n  - example-reader\nwelcome_issue: false\n','example-org','example-repo')
        self.assertEqual({u.username:u.permission for u in c.collaborators},{'example-admin':'admin','example-reader':'pull'})
        self.assertFalse(c.welcome_issue)
    def test_unknown_role_key_is_visible_before_sync(self):
        c=_parse_yaml_config('develoeprs:\n  - example-developer\n','example-org','example-repo')
        self.assertTrue(any('unknown key' in w for w in c.warnings));self.assertEqual(c.collaborators,[])
if __name__=='__main__':unittest.main(verbosity=2)
