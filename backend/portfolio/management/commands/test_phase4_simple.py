# backend/portfolio/management/commands/test_phase4_simple.py
"""
Simple Phase 4 API Test - Basic functionality verification
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from datetime import date, timedelta
from decimal import Decimal

from portfolio.models import Portfolio, Security, Transaction


class Command(BaseCommand):
    help = 'Simple test for Phase 4 API endpoints'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🧪 Simple Phase 4 API Test'))
        self.stdout.write(self.style.SUCCESS('=' * 40))

        # Setup
        user, created = User.objects.get_or_create(
            username='testuser',
            defaults={'email': 'test@example.com'}
        )

        portfolio, created = Portfolio.objects.get_or_create(
            name='Test Portfolio',
            user=user,
            defaults={'currency': 'USD'}
        )

        # Create API client
        client = APIClient()
        client.force_authenticate(user=user)

        # Test 1: Performance endpoint
        self.stdout.write('\n📊 Testing performance endpoint...')
        url = f'/api/portfolios/{portfolio.id}/performance/'
        response = client.get(url)

        if response.status_code == 200:
            self.stdout.write(self.style.SUCCESS('✅ Performance endpoint working'))
            data = response.json()
            self.stdout.write(f'   Portfolio: {data.get("portfolio_name")}')
            self.stdout.write(f'   Period: {data.get("period")}')
        else:
            self.stdout.write(self.style.ERROR(f'❌ Performance endpoint failed: {response.status_code}'))
            self.stdout.write(f'   Error: {response.content}')

        # Test 2: Summary endpoint
        self.stdout.write('\n📈 Testing summary endpoint...')
        url = f'/api/portfolios/{portfolio.id}/performance_summary/'
        response = client.get(url)

        if response.status_code == 200:
            self.stdout.write(self.style.SUCCESS('✅ Summary endpoint working'))
        else:
            self.stdout.write(self.style.ERROR(f'❌ Summary endpoint failed: {response.status_code}'))

        # Test 3: Recalculate endpoint
        self.stdout.write('\n🔄 Testing recalculate endpoint...')
        url = f'/api/portfolios/{portfolio.id}/recalculate_performance/'
        response = client.post(url, {'days': 7})

        if response.status_code == 200:
            self.stdout.write(self.style.SUCCESS('✅ Recalculate endpoint working'))
        else:
            self.stdout.write(self.style.ERROR(f'❌ Recalculate endpoint failed: {response.status_code}'))

        self.stdout.write(self.style.SUCCESS('\n🎉 Simple test complete!'))