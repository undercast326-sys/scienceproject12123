from django.contrib.auth.models import User
from rest_framework.test import APITestCase


class AuthTests(APITestCase):
    def test_register_returns_tokens_and_creates_profile(self):
        res = self.client.post('/api/auth/register/', {
            'username': 'newbie', 'email': 'n@example.com', 'password': 'pass12345',
        }, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertIn('access', res.data)
        self.assertIn('refresh', res.data)
        self.assertTrue(User.objects.get(username='newbie').password.startswith('argon2$'))

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        me = self.client.get('/api/progress/me/')
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data['username'], 'newbie')
        self.assertEqual(me.data['level'], 1)

    def test_login_and_refresh(self):
        User.objects.create_user('u', password='pass12345')
        res = self.client.post('/api/auth/login/', {'username': 'u', 'password': 'pass12345'}, format='json')
        self.assertEqual(res.status_code, 200)
        ref = self.client.post('/api/auth/login/refresh/', {'refresh': res.data['refresh']}, format='json')
        self.assertEqual(ref.status_code, 200)
        self.assertIn('access', ref.data)

    def test_unauthenticated_is_rejected(self):
        self.assertEqual(self.client.get('/api/topics/').status_code, 401)


class RegisterValidationTests(APITestCase):
    def register(self, **data):
        payload = {'username': 'newbie', 'email': '', 'password': 'Kq7!vLp2xZ'}
        payload.update(data)
        return self.client.post('/api/auth/register/', payload, format='json')

    def test_weak_passwords_are_rejected(self):
        for password in ('short1', '12345678', 'password123', 'newbie2024'):
            with self.subTest(password=password):
                res = self.register(password=password)
                self.assertEqual(res.status_code, 400)
                self.assertIn('password', res.data)
        self.assertFalse(User.objects.filter(username='newbie').exists())

    def test_duplicate_email_is_rejected_case_insensitively(self):
        User.objects.create_user('first', email='Taken@Example.com', password='x')
        res = self.register(email='taken@example.com')
        self.assertEqual(res.status_code, 400)
        self.assertIn('email', res.data)

    def test_email_stays_optional_for_many_users(self):
        self.assertEqual(self.register(username='a1').status_code, 201)
        self.assertEqual(self.register(username='a2').status_code, 201)

    def test_password_errors_are_in_russian(self):
        res = self.register(password='12345678')
        self.assertRegex(res.data['password'][0], '[а-яА-Я]')
