# Copyright 2013 Huawei Technologies Co.,LTD.
# All Rights Reserved.
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

from tempest.api.identity import base
from tempest.common.utils import data_utils
from tempest import test


class TokensTestJSON(base.BaseIdentityV2AdminTest):

    @test.idempotent_id('453ad4d5-e486-4b2f-be72-cffc8149e586')
    def test_create_get_delete_token(self):
        # get a token by username and password
        user_name = data_utils.rand_name(name='user')
        user_password = data_utils.rand_password()
        # first:create a tenant
        tenant_name = data_utils.rand_name(name='tenant')
        tenant = self.tenants_client.create_tenant(name=tenant_name)['tenant']
        # Delete the tenant at the end of the test
        self.addCleanup(self.tenants_client.delete_tenant, tenant['id'])
        # second:create a user
        user = self.users_client.create_user(name=user_name,
                                             password=user_password,
                                             tenantId=tenant['id'],
                                             email='')['user']
        # Delete the user at the end of the test
        self.addCleanup(self.users_client.delete_user, user['id'])
        # then get a token for the user
        body = self.token_client.auth(user_name,
                                      user_password,
                                      tenant['name'])
        self.assertEqual(body['token']['tenant']['name'],
                         tenant['name'])
        # Perform GET Token
        token_id = body['token']['id']
        token_details = self.client.show_token(token_id)['access']
        self.assertEqual(token_id, token_details['token']['id'])
        self.assertEqual(user['id'], token_details['user']['id'])
        self.assertEqual(user_name, token_details['user']['name'])
        self.assertEqual(tenant['name'],
                         token_details['token']['tenant']['name'])
        # then delete the token
        self.client.delete_token(token_id)

    @test.idempotent_id('25ba82ee-8a32-4ceb-8f50-8b8c71e8765e')
    def test_rescope_token(self):
        """An unscoped token can be requested

        That token can be used to request a scoped token.
        """

        # Create a user.
        user_name = data_utils.rand_name(name='user')
        user_password = data_utils.rand_password()
        tenant_id = None  # No default tenant so will get unscoped token.
        email = ''
        user = self.users_client.create_user(name=user_name,
                                             password=user_password,
                                             tenantId=tenant_id,
                                             email=email)['user']
        # Delete the user at the end of the test
        self.addCleanup(self.users_client.delete_user, user['id'])

        # Create a couple tenants.
        tenant1_name = data_utils.rand_name(name='tenant')
        tenant1 = self.tenants_client.create_tenant(
            name=tenant1_name)['tenant']
        # Delete the tenant at the end of the test
        self.addCleanup(self.tenants_client.delete_tenant, tenant1['id'])

        tenant2_name = data_utils.rand_name(name='tenant')
        tenant2 = self.tenants_client.create_tenant(
            name=tenant2_name)['tenant']
        # Delete the tenant at the end of the test
        self.addCleanup(self.tenants_client.delete_tenant, tenant2['id'])

        # Create a role
        role_name = data_utils.rand_name(name='role')
        role = self.roles_client.create_role(name=role_name)['role']
        # Delete the role at the end of the test
        self.addCleanup(self.roles_client.delete_role, role['id'])

        # Grant the user the role on the tenants.
        self.roles_client.create_user_role_on_project(tenant1['id'],
                                                      user['id'],
                                                      role['id'])

        self.roles_client.create_user_role_on_project(tenant2['id'],
                                                      user['id'],
                                                      role['id'])

        # Get an unscoped token.
        body = self.token_client.auth(user_name, user_password)

        token_id = body['token']['id']

        # Use the unscoped token to get a token scoped to tenant1
        body = self.token_client.auth_token(token_id,
                                            tenant=tenant1_name)

        scoped_token_id = body['token']['id']

        # Revoke the scoped token
        self.client.delete_token(scoped_token_id)

        # Use the unscoped token to get a token scoped to tenant2
        body = self.token_client.auth_token(token_id,
                                            tenant=tenant2_name)
