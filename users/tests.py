from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from .models import User, Fan


REGISTER_DATA = {
    'username': 'wanjiku',
    'email': 'wanjiku@example.com',
    'first_name': 'Wanjiku',
    'last_name': 'Kamau',
    'phone': '0712 345 678',
    'password': 'Str0ng-pass!',
}


class AuthTests(APITestCase):
    def register(self, **overrides):
        return self.client.post('/api/auth/register/', {**REGISTER_DATA, **overrides})

    def login(self, username='wanjiku', password='Str0ng-pass!'):
        return self.client.post('/api/auth/login/', {'username': username, 'password': password})

    def test_register_creates_fan_and_returns_tokens(self):
        res = self.register()
        self.assertEqual(res.status_code, 201, res.data)
        self.assertIn('access', res.data)
        self.assertIn('refresh', res.data)
        self.assertNotIn('password', res.data['user'])

        user = User.objects.get(username='wanjiku')
        self.assertEqual(user.role, 'fan')
        self.assertEqual(user.phone, '254712345678')
        self.assertTrue(user.check_password('Str0ng-pass!'))
        self.assertTrue(Fan.objects.filter(user=user).exists())

    def test_register_cannot_choose_role(self):
        self.register(role='admin')
        self.assertEqual(User.objects.get(username='wanjiku').role, 'fan')

    def test_register_rejects_duplicate_email(self):
        self.register()
        res = self.register(username='other', email='WANJIKU@example.com')
        self.assertEqual(res.status_code, 400)
        self.assertIn('email', res.data)

    def test_register_rejects_bad_phone(self):
        res = self.register(phone='12345')
        self.assertEqual(res.status_code, 400)
        self.assertIn('phone', res.data)

    def test_register_rejects_weak_password(self):
        res = self.register(password='123')
        self.assertEqual(res.status_code, 400)

    def test_phone_formats_are_normalized(self):
        for i, phone in enumerate(['+254712345678', '254112345678', '0112345678']):
            res = self.register(username=f'u{i}', email=f'u{i}@example.com', phone=phone)
            self.assertEqual(res.status_code, 201, res.data)
            self.assertRegex(res.data['user']['phone'], r'^254[17]\d{8}$')

    def test_login_returns_tokens_with_role(self):
        self.register()
        res = self.login()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['user']['username'], 'wanjiku')
        token = AccessToken(res.data['access'])
        self.assertEqual(token['role'], 'fan')

    def test_login_wrong_password(self):
        self.register()
        self.assertEqual(self.login(password='wrong').status_code, 401)

    def test_me_requires_authentication(self):
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)

    def test_me_identifies_the_logged_in_fan(self):
        access = self.register().data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        res = self.client.get('/api/auth/me/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['username'], 'wanjiku')

    def test_me_update_cannot_change_role(self):
        access = self.register().data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        res = self.client.patch('/api/auth/me/', {'first_name': 'Njeri', 'role': 'admin'})
        self.assertEqual(res.status_code, 200)
        user = User.objects.get(username='wanjiku')
        self.assertEqual((user.first_name, user.role), ('Njeri', 'fan'))

    def test_refresh_then_logout_blacklists_token(self):
        tokens = self.register().data
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

        res = self.client.post('/api/auth/refresh/', {'refresh': tokens['refresh']})
        self.assertEqual(res.status_code, 200)
        refresh = res.data['refresh']  # rotated

        self.assertEqual(self.client.post('/api/auth/logout/', {'refresh': refresh}).status_code, 205)
        self.assertEqual(self.client.post('/api/auth/refresh/', {'refresh': refresh}).status_code, 401)
