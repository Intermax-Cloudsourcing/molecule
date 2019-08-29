#  Copyright (c) 2015-2018 Cisco Systems, Inc.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to
#  deal in the Software without restriction, including without limitation the
#  rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
#  sell copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in
#  all copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#  DEALINGS IN THE SOFTWARE.

import collections
import os

import pytest

from molecule import config
from molecule import util
from molecule.provisioner import ansible
from molecule.provisioner import ansible_playbooks
from molecule.provisioner.lint import ansible_lint


@pytest.fixture
def _patched_ansible_playbook(mocker):
    m = mocker.patch('molecule.provisioner.ansible_playbook.AnsiblePlaybook')
    m.return_value.execute.return_value = b'patched-ansible-playbook-stdout'

    return m


@pytest.fixture
def _patched_write_inventory(mocker):
    return mocker.patch('molecule.provisioner.ansible.Ansible._write_inventory')


@pytest.fixture
def _patched_remove_vars(mocker):
    return mocker.patch('molecule.provisioner.ansible.Ansible._remove_vars')


@pytest.fixture
def _patched_link_or_update_vars(mocker):
    return mocker.patch('molecule.provisioner.ansible.Ansible._link_or_update_vars')


@pytest.fixture
def _provisioner_section_data():
    return {
        'provisioner': {
            'name': 'ansible',
            'config_options': {'defaults': {'foo': 'bar'}},
            'connection_options': {'foo': 'bar'},
            'options': {'foo': 'bar', 'become': True, 'v': True},
            'env': {
                'FOO': 'bar',
                'ANSIBLE_ROLES_PATH': 'foo/bar',
                'ANSIBLE_LIBRARY': 'foo/bar',
                'ANSIBLE_FILTER_PLUGINS': 'foo/bar',
            },
            'inventory': {
                'hosts': {
                    'all': {
                        'hosts': {'extra-host-01': {}},
                        'children': {'extra-group': {'hosts': ['extra-host-01']}},
                    }
                },
                'host_vars': {
                    'instance-1': [{'foo': 'bar'}],
                    'localhost': [{'foo': 'baz'}],
                },
                'group_vars': {
                    'example_group1': [{'foo': 'bar'}],
                    'example_group2': [{'foo': 'bar'}],
                },
            },
            'lint': {'name': 'ansible-lint'},
        }
    }


@pytest.fixture
def _instance(_provisioner_section_data, config_instance):
    return ansible.Ansible(config_instance)


def test_config_private_member(_instance):
    assert isinstance(_instance._config, config.Config)


def test_default_config_options_property(_instance):
    x = {
        'defaults': {
            'ansible_managed': 'Ansible managed: Do NOT edit this file manually!',
            'retry_files_enabled': False,
            'host_key_checking': False,
            'nocows': 1,
        },
        'ssh_connection': {
            'scp_if_ssh': True,
            'control_path': '%(directory)s/%%h-%%p-%%r',
        },
    }

    assert x == _instance.default_config_options


def test_default_options_property(_instance):
    assert {'skip-tags': 'molecule-notest,notest'} == _instance.default_options


def test_default_env_property(_instance):
    x = _instance._config.provisioner.config_file

    assert x == _instance.default_env['ANSIBLE_CONFIG']
    assert 'MOLECULE_FILE' in _instance.default_env
    assert 'MOLECULE_INVENTORY_FILE' in _instance.default_env
    assert 'MOLECULE_SCENARIO_DIRECTORY' in _instance.default_env
    assert 'MOLECULE_INSTANCE_CONFIG' in _instance.default_env
    assert 'ANSIBLE_CONFIG' in _instance.env
    assert 'ANSIBLE_ROLES_PATH' in _instance.env
    assert 'ANSIBLE_LIBRARY' in _instance.env
    assert 'ANSIBLE_FILTER_PLUGINS' in _instance.env


def test_name_property(_instance):
    assert 'ansible' == _instance.name


def test_lint_property(_instance):
    assert isinstance(_instance.lint, ansible_lint.AnsibleLint)


@pytest.mark.parametrize(
    'config_instance', ['_provisioner_section_data'], indirect=True
)
def test_config_options_property(_instance):
    x = {
        'defaults': {
            'ansible_managed': 'Ansible managed: Do NOT edit this file manually!',
            'retry_files_enabled': False,
            'host_key_checking': False,
            'nocows': 1,
            'foo': 'bar',
        },
        'ssh_connection': {
            'scp_if_ssh': True,
            'control_path': '%(directory)s/%%h-%%p-%%r',
        },
    }

    assert x == _instance.config_options


@pytest.mark.parametrize(
    'config_instance', ['_provisioner_section_data'], indirect=True
)
def test_options_property(_instance):
    x = {'become': True, 'foo': 'bar', 'v': True, 'skip-tags': 'molecule-notest,notest'}

    assert x == _instance.options


def test_options_property_does_not_merge(_instance):
    for action in ['create', 'destroy']:
        _instance._config.action = action

        assert {'skip-tags': 'molecule-notest,notest'} == _instance.options


def test_options_property_handles_cli_args(_instance):
    _instance._config.args = {'debug': True}
    x = {
        'vvv': True,
        'become': True,
        'diff': True,
        'skip-tags': 'molecule-notest,notest',
    }

    assert x == _instance.options


@pytest.mark.parametrize(
    'config_instance', ['_provisioner_section_data'], indirect=True
)
def test_env_property(_instance):
    x = _instance._config.provisioner.config_file

    assert x == _instance.env['ANSIBLE_CONFIG']
    assert 'bar' == _instance.env['FOO']


@pytest.mark.parametrize(
    'config_instance', ['_provisioner_section_data'], indirect=True
)
def test_env_appends_env_property(_instance):
    x = [
        util.abs_path(
            os.path.join(_instance._config.scenario.ephemeral_directory, 'roles')
        ),
        util.abs_path(
            os.path.join(_instance._config.project_directory, os.path.pardir)
        ),
        util.abs_path(os.path.join(_instance._config.scenario.directory, 'foo', 'bar')),
    ]
    assert x == _instance.env['ANSIBLE_ROLES_PATH'].split(':')

    x = [
        _instance._get_modules_directory(),
        util.abs_path(
            os.path.join(_instance._config.scenario.ephemeral_directory, 'modules')
        ),
        util.abs_path(os.path.join(_instance._config.project_directory, 'modules')),
        util.abs_path(os.path.join(_instance._config.scenario.directory, 'foo', 'bar')),
    ]
    assert x == _instance.env['ANSIBLE_LIBRARY'].split(':')

    x = [
        _instance._get_filter_plugin_directory(),
        util.abs_path(
            os.path.join(
                _instance._config.scenario.ephemeral_directory, 'plugins', 'filter'
            )
        ),
        util.abs_path(
            os.path.join(_instance._config.project_directory, 'plugins', 'filter')
        ),
        util.abs_path(os.path.join(_instance._config.scenario.directory, 'foo', 'bar')),
    ]
    assert x == _instance.env['ANSIBLE_FILTER_PLUGINS'].split(':')


@pytest.mark.parametrize(
    'config_instance', ['_provisioner_section_data'], indirect=True
)
def test_host_vars_property(_instance):
    x = {'instance-1': [{'foo': 'bar'}], 'localhost': [{'foo': 'baz'}]}

    assert x == _instance.host_vars


@pytest.mark.parametrize(
    'config_instance', ['_provisioner_section_data'], indirect=True
)
def test_group_vars_property(_instance):
    x = {'example_group1': [{'foo': 'bar'}], 'example_group2': [{'foo': 'bar'}]}

    assert x == _instance.group_vars


@pytest.mark.parametrize(
    'config_instance', ['_provisioner_section_data'], indirect=True
)
def test_hosts_property(_instance):
    hosts = {
        'all': {
            'hosts': {'extra-host-01': {}},
            'children': {'extra-group': {'hosts': ['extra-host-01']}},
        }
    }

    assert hosts == _instance.hosts


def test_links_property(_instance):
    assert {} == _instance.links


@pytest.mark.parametrize(
    'config_instance', ['_provisioner_section_data'], indirect=True
)
def test_inventory_property(_instance):
    x = {
        'ungrouped': {'vars': {}},
        'bar': {
            'hosts': {'instance-1': {'foo': 'bar', 'ansible_connection': 'docker'}},
            'children': {
                'child1': {
                    'hosts': {
                        'instance-1': {'foo': 'bar', 'ansible_connection': 'docker'}
                    }
                }
            },
            'vars': {
                'molecule_file': "{{ lookup('env', 'MOLECULE_FILE') }}",
                'molecule_base_file': "{{ lookup('env', 'MOLECULE_BASE_FILE') }}",
                'molecule_ephemeral_directory': "{{ lookup('env', 'MOLECULE_EPHEMERAL_DIRECTORY') }}",
                'molecule_scenario_directory': "{{ lookup('env', 'MOLECULE_SCENARIO_DIRECTORY') }}",
                'molecule_yml': "{{ lookup('file', molecule_file) | molecule_from_yaml }}",
                'molecule_instance_config': "{{ lookup('env', 'MOLECULE_INSTANCE_CONFIG') }}",
                'molecule_no_log': "{{ lookup('env', 'MOLECULE_NO_LOG') or not "
                "molecule_yml.provisioner.log|default(False) | bool }}",
            },
        },
        'all': {
            'hosts': {
                'instance-1': {'foo': 'bar', 'ansible_connection': 'docker'},
                'instance-2': {'foo': 'bar', 'ansible_connection': 'docker'},
            },
            'vars': {
                'molecule_file': "{{ lookup('env', 'MOLECULE_FILE') }}",
                'molecule_base_file': "{{ lookup('env', 'MOLECULE_BASE_FILE') }}",
                'molecule_ephemeral_directory': "{{ lookup('env', 'MOLECULE_EPHEMERAL_DIRECTORY') }}",
                'molecule_scenario_directory': "{{ lookup('env', 'MOLECULE_SCENARIO_DIRECTORY') }}",
                'molecule_yml': "{{ lookup('file', molecule_file) | molecule_from_yaml }}",
                'molecule_instance_config': "{{ lookup('env', 'MOLECULE_INSTANCE_CONFIG') }}",
                'molecule_no_log': "{{ lookup('env', 'MOLECULE_NO_LOG') or not "
                "molecule_yml.provisioner.log|default(False) | bool }}",
            },
        },
        'foo': {
            'hosts': {
                'instance-1': {'foo': 'bar', 'ansible_connection': 'docker'},
                'instance-2': {'foo': 'bar', 'ansible_connection': 'docker'},
            },
            'children': {
                'child1': {
                    'hosts': {
                        'instance-1': {'foo': 'bar', 'ansible_connection': 'docker'}
                    }
                },
                'child2': {
                    'hosts': {
                        'instance-2': {'foo': 'bar', 'ansible_connection': 'docker'}
                    }
                },
            },
            'vars': {
                'molecule_file': "{{ lookup('env', 'MOLECULE_FILE') }}",
                'molecule_base_file': "{{ lookup('env', 'MOLECULE_BASE_FILE') }}",
                'molecule_ephemeral_directory': "{{ lookup('env', 'MOLECULE_EPHEMERAL_DIRECTORY') }}",
                'molecule_scenario_directory': "{{ lookup('env', 'MOLECULE_SCENARIO_DIRECTORY') }}",
                'molecule_yml': "{{ lookup('file', molecule_file) | molecule_from_yaml }}",
                'molecule_instance_config': "{{ lookup('env', 'MOLECULE_INSTANCE_CONFIG') }}",
                'molecule_no_log': "{{ lookup('env', 'MOLECULE_NO_LOG') or not "
                "molecule_yml.provisioner.log|default(False) | bool }}",
            },
        },
        'baz': {
            'hosts': {'instance-2': {'foo': 'bar', 'ansible_connection': 'docker'}},
            'children': {
                'child2': {
                    'hosts': {
                        'instance-2': {'foo': 'bar', 'ansible_connection': 'docker'}
                    }
                }
            },
            'vars': {
                'molecule_file': "{{ lookup('env', 'MOLECULE_FILE') }}",
                'molecule_base_file': "{{ lookup('env', 'MOLECULE_BASE_FILE') }}",
                'molecule_ephemeral_directory': "{{ lookup('env', 'MOLECULE_EPHEMERAL_DIRECTORY') }}",
                'molecule_scenario_directory': "{{ lookup('env', 'MOLECULE_SCENARIO_DIRECTORY') }}",
                'molecule_yml': "{{ lookup('file', molecule_file) | molecule_from_yaml }}",
                'molecule_instance_config': "{{ lookup('env', 'MOLECULE_INSTANCE_CONFIG') }}",
                'molecule_no_log': "{{ lookup('env', 'MOLECULE_NO_LOG') or not "
                "molecule_yml.provisioner.log|default(False) | bool }}",
            },
        },
    }

    assert x == _instance.inventory


@pytest.mark.parametrize(
    'config_instance', ['_provisioner_section_data'], indirect=True
)
def test_inventory_property_handles_missing_groups(temp_dir, _instance):
    platforms = [{'name': 'instance-1'}, {'name': 'instance-2'}]
    _instance._config.config['platforms'] = platforms

    x = {
        'ungrouped': {
            'hosts': {
                'instance-1': {'foo': 'bar', 'ansible_connection': 'docker'},
                'instance-2': {'foo': 'bar', 'ansible_connection': 'docker'},
            },
            'vars': {},
        },
        'all': {
            'hosts': {
                'instance-1': {'foo': 'bar', 'ansible_connection': 'docker'},
                'instance-2': {'foo': 'bar', 'ansible_connection': 'docker'},
            },
            'vars': {
                'molecule_file': "{{ lookup('env', 'MOLECULE_FILE') }}",
                'molecule_base_file': "{{ lookup('env', 'MOLECULE_BASE_FILE') }}",
                'molecule_ephemeral_directory': "{{ lookup('env', 'MOLECULE_EPHEMERAL_DIRECTORY') }}",
                'molecule_scenario_directory': "{{ lookup('env', 'MOLECULE_SCENARIO_DIRECTORY') }}",
                'molecule_yml': "{{ lookup('file', molecule_file) | molecule_from_yaml }}",
                'molecule_instance_config': "{{ lookup('env', 'MOLECULE_INSTANCE_CONFIG') }}",
                'molecule_no_log': "{{ lookup('env', 'MOLECULE_NO_LOG') or not "
                "molecule_yml.provisioner.log|default(False) | bool }}",
            },
        },
    }

    assert x == _instance.inventory


def test_inventory_directory_property(_instance):
    x = os.path.join(_instance._config.scenario.ephemeral_directory, 'inventory')
    assert x == _instance.inventory_directory


def test_inventory_file_property(_instance):
    x = os.path.join(
        _instance._config.scenario.inventory_directory, 'ansible_inventory.yml'
    )

    assert x == _instance.inventory_file


def test_config_file_property(_instance):
    x = os.path.join(_instance._config.scenario.ephemeral_directory, 'ansible.cfg')

    assert x == _instance.config_file


def test_playbooks_property(_instance):
    assert isinstance(_instance.playbooks, ansible_playbooks.AnsiblePlaybooks)


def test_directory_property(_instance):
    result = _instance.directory
    parts = pytest.helpers.os_split(result)

    assert ('molecule', 'provisioner', 'ansible') == parts[-3:]


def test_playbooks_cleaned_property_is_optional(_instance):
    assert _instance.playbooks.cleanup is None


def test_playbooks_create_property(_instance):
    x = os.path.join(
        _instance._config.provisioner.playbooks._get_playbook_directory(),
        'docker',
        'create.yml',
    )

    assert x == _instance.playbooks.create


def test_playbooks_converge_property(_instance):
    x = os.path.join(_instance._config.scenario.directory, 'playbook.yml')

    assert x == _instance.playbooks.converge


def test_playbooks_destroy_property(_instance):
    x = os.path.join(
        _instance._config.provisioner.playbooks._get_playbook_directory(),
        'docker',
        'destroy.yml',
    )

    assert x == _instance.playbooks.destroy


def test_playbooks_side_effect_property(_instance):
    assert _instance.playbooks.side_effect is None


@pytest.mark.parametrize(
    'config_instance', ['_provisioner_section_data'], indirect=True
)
def test_connection_options(_instance):
    x = {'ansible_connection': 'docker', 'foo': 'bar'}

    assert x == _instance.connection_options('foo')


def test_check(_instance, mocker, _patched_ansible_playbook):
    _instance.check()

    _patched_ansible_playbook.assert_called_once_with(
        _instance._config.provisioner.playbooks.converge, _instance._config
    )
    _patched_ansible_playbook.return_value.add_cli_arg.assert_called_once_with(
        'check', True
    )
    _patched_ansible_playbook.return_value.execute.assert_called_once_with()


def test_converge(_instance, mocker, _patched_ansible_playbook):
    result = _instance.converge()

    _patched_ansible_playbook.assert_called_once_with(
        _instance._config.provisioner.playbooks.converge, _instance._config
    )
    # NOTE(retr0h): This is not the true return type.  This is a mock return
    #               which didn't go through str.decode().
    assert result == b'patched-ansible-playbook-stdout'

    _patched_ansible_playbook.return_value.execute.assert_called_once_with()


def test_converge_with_playbook(_instance, mocker, _patched_ansible_playbook):
    result = _instance.converge('playbook')

    _patched_ansible_playbook.assert_called_once_with('playbook', _instance._config)
    # NOTE(retr0h): This is not the true return type.  This is a mock return
    #               which didn't go through str.decode().
    assert result == b'patched-ansible-playbook-stdout'

    _patched_ansible_playbook.return_value.execute.assert_called_once_with()


def test_cleanup(_instance, mocker, _patched_ansible_playbook):
    _instance.cleanup()

    _patched_ansible_playbook.assert_called_once_with(
        _instance._config.provisioner.playbooks.cleanup, _instance._config
    )
    _patched_ansible_playbook.return_value.execute.assert_called_once_with()


def test_destroy(_instance, mocker, _patched_ansible_playbook):
    _instance.destroy()

    _patched_ansible_playbook.assert_called_once_with(
        _instance._config.provisioner.playbooks.destroy, _instance._config
    )
    _patched_ansible_playbook.return_value.execute.assert_called_once_with()


def test_side_effect(_instance, mocker, _patched_ansible_playbook):
    _instance.side_effect()

    _patched_ansible_playbook.assert_called_once_with(
        _instance._config.provisioner.playbooks.side_effect, _instance._config
    )
    _patched_ansible_playbook.return_value.execute.assert_called_once_with()


def test_create(_instance, mocker, _patched_ansible_playbook):
    _instance.create()

    _patched_ansible_playbook.assert_called_once_with(
        _instance._config.provisioner.playbooks.create, _instance._config
    )
    _patched_ansible_playbook.return_value.execute.assert_called_once_with()


def test_prepare(_instance, mocker, _patched_ansible_playbook):
    _instance.prepare()

    _patched_ansible_playbook.assert_called_once_with(
        _instance._config.provisioner.playbooks.prepare, _instance._config
    )
    _patched_ansible_playbook.return_value.execute.assert_called_once_with()


def test_syntax(_instance, mocker, _patched_ansible_playbook):
    _instance.syntax()

    _patched_ansible_playbook.assert_called_once_with(
        _instance._config.provisioner.playbooks.converge, _instance._config
    )
    _patched_ansible_playbook.return_value.add_cli_arg.assert_called_once_with(
        'syntax-check', True
    )
    _patched_ansible_playbook.return_value.execute.assert_called_once_with()


def test_verify(_instance, mocker, _patched_ansible_playbook):
    _instance.verify()

    _patched_ansible_playbook.assert_called_once_with(
        _instance._config.provisioner.playbooks.verify, _instance._config
    )
    _patched_ansible_playbook.return_value.execute.assert_called_once_with()


def test_write_config(temp_dir, _instance):
    _instance.write_config()

    assert os.path.isfile(_instance.config_file)


def test_manage_inventory(
    _instance,
    _patched_write_inventory,
    _patched_remove_vars,
    patched_add_or_update_vars,
    _patched_link_or_update_vars,
):
    _instance.manage_inventory()

    _patched_write_inventory.assert_called_once_with()
    _patched_remove_vars.assert_called_once_with()
    patched_add_or_update_vars.assert_called_once_with()
    assert not _patched_link_or_update_vars.called


def test_manage_inventory_with_links(
    _instance,
    _patched_write_inventory,
    _patched_remove_vars,
    patched_add_or_update_vars,
    _patched_link_or_update_vars,
):
    c = _instance._config.config
    c['provisioner']['inventory']['links'] = {'foo': 'bar'}
    _instance.manage_inventory()

    _patched_write_inventory.assert_called_once_with()
    _patched_remove_vars.assert_called_once_with()
    assert not patched_add_or_update_vars.called
    _patched_link_or_update_vars.assert_called_once_with()


@pytest.mark.parametrize(
    'config_instance', ['_provisioner_section_data'], indirect=True
)
def test_add_or_update_vars(_instance):
    inventory_dir = _instance._config.scenario.inventory_directory

    host_vars_directory = os.path.join(inventory_dir, 'host_vars')
    host_vars = os.path.join(host_vars_directory, 'instance-1')

    _instance._add_or_update_vars()

    assert os.path.isdir(host_vars_directory)
    assert os.path.isfile(host_vars)

    host_vars_localhost = os.path.join(host_vars_directory, 'localhost')
    assert os.path.isfile(host_vars_localhost)

    group_vars_directory = os.path.join(inventory_dir, 'group_vars')
    group_vars_1 = os.path.join(group_vars_directory, 'example_group1')
    group_vars_2 = os.path.join(group_vars_directory, 'example_group2')

    assert os.path.isdir(group_vars_directory)
    assert os.path.isfile(group_vars_1)
    assert os.path.isfile(group_vars_2)

    hosts = os.path.join(inventory_dir, 'hosts')
    assert os.path.isfile(hosts)
    assert util.safe_load_file(hosts) == _instance.hosts


@pytest.mark.parametrize(
    'config_instance', ['_provisioner_section_data'], indirect=True
)
def test_add_or_update_vars_without_host_vars(_instance):
    c = _instance._config.config
    c['provisioner']['inventory']['host_vars'] = {}
    inventory_dir = _instance._config.scenario.inventory_directory

    host_vars_directory = os.path.join(inventory_dir, 'host_vars')
    host_vars = os.path.join(host_vars_directory, 'instance-1')

    _instance._add_or_update_vars()

    assert not os.path.isdir(host_vars_directory)
    assert not os.path.isfile(host_vars)

    host_vars_localhost = os.path.join(host_vars_directory, 'localhost')
    assert not os.path.isfile(host_vars_localhost)

    group_vars_directory = os.path.join(inventory_dir, 'group_vars')
    group_vars_1 = os.path.join(group_vars_directory, 'example_group1')
    group_vars_2 = os.path.join(group_vars_directory, 'example_group2')

    assert os.path.isdir(group_vars_directory)
    assert os.path.isfile(group_vars_1)
    assert os.path.isfile(group_vars_2)

    hosts = os.path.join(inventory_dir, 'hosts')
    assert os.path.isfile(hosts)
    assert util.safe_load_file(hosts) == _instance.hosts


def test_add_or_update_vars_does_not_create_vars(_instance):
    c = _instance._config.config
    c['provisioner']['inventory']['hosts'] = {}
    c['provisioner']['inventory']['host_vars'] = {}
    c['provisioner']['inventory']['group_vars'] = {}
    inventory_dir = _instance._config.scenario.inventory_directory

    hosts = os.path.join(inventory_dir, 'hosts')
    host_vars_directory = os.path.join(inventory_dir, 'host_vars')
    group_vars_directory = os.path.join(inventory_dir, 'group_vars')

    _instance._add_or_update_vars()

    assert not os.path.isdir(host_vars_directory)
    assert not os.path.isdir(group_vars_directory)
    assert not os.path.isfile(hosts)


@pytest.mark.parametrize(
    'config_instance', ['_provisioner_section_data'], indirect=True
)
def test_write_inventory(temp_dir, _instance):
    _instance._write_inventory()

    assert os.path.isfile(_instance.inventory_file)

    data = util.safe_load_file(_instance.inventory_file)

    x = {
        'ungrouped': {'vars': {}},
        'bar': {
            'hosts': {'instance-1': {'foo': 'bar', 'ansible_connection': 'docker'}},
            'children': {
                'child1': {
                    'hosts': {
                        'instance-1': {'foo': 'bar', 'ansible_connection': 'docker'}
                    }
                }
            },
            'vars': {
                'molecule_file': "{{ lookup('env', 'MOLECULE_FILE') }}",
                'molecule_base_file': "{{ lookup('env', 'MOLECULE_BASE_FILE') }}",
                'molecule_ephemeral_directory': "{{ lookup('env', 'MOLECULE_EPHEMERAL_DIRECTORY') }}",
                'molecule_scenario_directory': "{{ lookup('env', 'MOLECULE_SCENARIO_DIRECTORY') }}",
                'molecule_yml': "{{ lookup('file', molecule_file) | molecule_from_yaml }}",
                'molecule_instance_config': "{{ lookup('env', 'MOLECULE_INSTANCE_CONFIG') }}",
                'molecule_no_log': "{{ lookup('env', 'MOLECULE_NO_LOG') or not "
                "molecule_yml.provisioner.log|default(False) | bool }}",
            },
        },
        'all': {
            'hosts': {
                'instance-1': {'foo': 'bar', 'ansible_connection': 'docker'},
                'instance-2': {'foo': 'bar', 'ansible_connection': 'docker'},
            },
            'vars': {
                'molecule_file': "{{ lookup('env', 'MOLECULE_FILE') }}",
                'molecule_base_file': "{{ lookup('env', 'MOLECULE_BASE_FILE') }}",
                'molecule_ephemeral_directory': "{{ lookup('env', 'MOLECULE_EPHEMERAL_DIRECTORY') }}",
                'molecule_scenario_directory': "{{ lookup('env', 'MOLECULE_SCENARIO_DIRECTORY') }}",
                'molecule_yml': "{{ lookup('file', molecule_file) | molecule_from_yaml }}",
                'molecule_instance_config': "{{ lookup('env', 'MOLECULE_INSTANCE_CONFIG') }}",
                'molecule_no_log': "{{ lookup('env', 'MOLECULE_NO_LOG') or not "
                "molecule_yml.provisioner.log|default(False) | bool }}",
            },
        },
        'foo': {
            'hosts': {
                'instance-1': {'foo': 'bar', 'ansible_connection': 'docker'},
                'instance-2': {'foo': 'bar', 'ansible_connection': 'docker'},
            },
            'children': {
                'child1': {
                    'hosts': {
                        'instance-1': {'foo': 'bar', 'ansible_connection': 'docker'}
                    }
                },
                'child2': {
                    'hosts': {
                        'instance-2': {'foo': 'bar', 'ansible_connection': 'docker'}
                    }
                },
            },
            'vars': {
                'molecule_file': "{{ lookup('env', 'MOLECULE_FILE') }}",
                'molecule_base_file': "{{ lookup('env', 'MOLECULE_BASE_FILE') }}",
                'molecule_ephemeral_directory': "{{ lookup('env', 'MOLECULE_EPHEMERAL_DIRECTORY') }}",
                'molecule_scenario_directory': "{{ lookup('env', 'MOLECULE_SCENARIO_DIRECTORY') }}",
                'molecule_yml': "{{ lookup('file', molecule_file) | molecule_from_yaml }}",
                'molecule_instance_config': "{{ lookup('env', 'MOLECULE_INSTANCE_CONFIG') }}",
                'molecule_no_log': "{{ lookup('env', 'MOLECULE_NO_LOG') or not "
                "molecule_yml.provisioner.log|default(False) | bool }}",
            },
        },
        'baz': {
            'hosts': {'instance-2': {'foo': 'bar', 'ansible_connection': 'docker'}},
            'children': {
                'child2': {
                    'hosts': {
                        'instance-2': {'foo': 'bar', 'ansible_connection': 'docker'}
                    }
                }
            },
            'vars': {
                'molecule_file': "{{ lookup('env', 'MOLECULE_FILE') }}",
                'molecule_base_file': "{{ lookup('env', 'MOLECULE_BASE_FILE') }}",
                'molecule_ephemeral_directory': "{{ lookup('env', 'MOLECULE_EPHEMERAL_DIRECTORY') }}",
                'molecule_scenario_directory': "{{ lookup('env', 'MOLECULE_SCENARIO_DIRECTORY') }}",
                'molecule_yml': "{{ lookup('file', molecule_file) | molecule_from_yaml }}",
                'molecule_instance_config': "{{ lookup('env', 'MOLECULE_INSTANCE_CONFIG') }}",
                'molecule_no_log': "{{ lookup('env', 'MOLECULE_NO_LOG') or not "
                "molecule_yml.provisioner.log|default(False) | bool }}",
            },
        },
    }

    assert x == data


@pytest.mark.parametrize(
    'config_instance', ['_provisioner_section_data'], indirect=True
)
def test_remove_vars(_instance):
    inventory_dir = _instance._config.scenario.inventory_directory

    hosts = os.path.join(inventory_dir, 'hosts')
    host_vars_directory = os.path.join(inventory_dir, 'host_vars')
    host_vars = os.path.join(host_vars_directory, 'instance-1')

    _instance._add_or_update_vars()
    assert os.path.isfile(hosts)
    assert os.path.isdir(host_vars_directory)
    assert os.path.isfile(host_vars)

    host_vars_localhost = os.path.join(host_vars_directory, 'localhost')
    assert os.path.isfile(host_vars_localhost)

    group_vars_directory = os.path.join(inventory_dir, 'group_vars')
    group_vars_1 = os.path.join(group_vars_directory, 'example_group1')
    group_vars_2 = os.path.join(group_vars_directory, 'example_group2')

    assert os.path.isdir(group_vars_directory)
    assert os.path.isfile(group_vars_1)
    assert os.path.isfile(group_vars_2)

    _instance._remove_vars()

    assert not os.path.isfile(hosts)
    assert not os.path.isdir(host_vars_directory)
    assert not os.path.isdir(group_vars_directory)


def test_remove_vars_symlinks(_instance):
    inventory_dir = _instance._config.scenario.inventory_directory

    source_group_vars = os.path.join(inventory_dir, os.path.pardir, 'group_vars')
    target_group_vars = os.path.join(inventory_dir, 'group_vars')
    os.mkdir(source_group_vars)
    os.symlink(source_group_vars, target_group_vars)

    _instance._remove_vars()

    assert not os.path.lexists(target_group_vars)


def test_link_vars(_instance):
    c = _instance._config.config
    c['provisioner']['inventory']['links'] = {
        'hosts': '../hosts',
        'group_vars': '../group_vars',
        'host_vars': '../host_vars',
    }
    inventory_dir = _instance._config.scenario.inventory_directory
    scenario_dir = _instance._config.scenario.directory
    source_hosts = os.path.join(scenario_dir, os.path.pardir, 'hosts')
    target_hosts = os.path.join(inventory_dir, 'hosts')
    source_group_vars = os.path.join(scenario_dir, os.path.pardir, 'group_vars')
    target_group_vars = os.path.join(inventory_dir, 'group_vars')
    source_host_vars = os.path.join(scenario_dir, os.path.pardir, 'host_vars')
    target_host_vars = os.path.join(inventory_dir, 'host_vars')

    open(source_hosts, 'w').close()
    os.mkdir(source_group_vars)
    os.mkdir(source_host_vars)

    _instance._link_or_update_vars()

    assert os.path.lexists(target_hosts)
    assert os.path.lexists(target_group_vars)
    assert os.path.lexists(target_host_vars)


def test_link_vars_raises_when_source_not_found(_instance, patched_logger_critical):
    c = _instance._config.config
    c['provisioner']['inventory']['links'] = {'foo': '../bar'}

    with pytest.raises(SystemExit) as e:
        _instance._link_or_update_vars()

    assert 1 == e.value.code

    source = os.path.join(_instance._config.scenario.directory, os.path.pardir, 'bar')
    msg = "The source path '{}' does not exist.".format(source)
    patched_logger_critical.assert_called_once_with(msg)


def test_verify_inventory(_instance):
    _instance._verify_inventory()


def test_verify_inventory_raises_when_missing_hosts(
    temp_dir, patched_logger_critical, _instance
):
    _instance._config.config['platforms'] = []
    with pytest.raises(SystemExit) as e:
        _instance._verify_inventory()

    assert 1 == e.value.code

    msg = "Instances missing from the 'platform' section of molecule.yml."
    patched_logger_critical.assert_called_once_with(msg)


def test_vivify(_instance):
    d = _instance._vivify()
    d['bar']['baz'] = 'qux'

    assert 'qux' == str(d['bar']['baz'])


def test_default_to_regular(_instance):
    d = collections.defaultdict()
    assert isinstance(d, collections.defaultdict)

    d = _instance._default_to_regular(d)
    assert isinstance(d, dict)


def test_get_plugin_directory(_instance):
    result = _instance._get_plugin_directory()
    parts = pytest.helpers.os_split(result)

    assert ('molecule', 'provisioner', 'ansible', 'plugins') == parts[-4:]


def test_get_modules_directory(_instance):
    result = _instance._get_modules_directory()
    parts = pytest.helpers.os_split(result)
    x = ('molecule', 'provisioner', 'ansible', 'plugins', 'modules')

    assert x == parts[-5:]


def test_get_filter_plugin_directory(_instance):
    result = _instance._get_filter_plugin_directory()
    parts = pytest.helpers.os_split(result)
    x = ('molecule', 'provisioner', 'ansible', 'plugins', 'filter')

    assert x == parts[-5:]


def test_absolute_path_for(_instance):
    env = {'foo': 'foo:bar'}
    x = ':'.join(
        [
            os.path.join(_instance._config.scenario.directory, 'foo'),
            os.path.join(_instance._config.scenario.directory, 'bar'),
        ]
    )

    assert x == _instance._absolute_path_for(env, 'foo')


def test_absolute_path_for_raises_with_missing_key(_instance):
    env = {'foo': 'foo:bar'}

    with pytest.raises(KeyError):
        _instance._absolute_path_for(env, 'invalid')
