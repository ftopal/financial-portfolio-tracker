from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PortfolioViewSet, AssetCategoryViewSet, SecurityViewSet,
    TransactionViewSet, CashTransactionViewSet, UserPreferencesViewSet,
    portfolio_summary, portfolio_holdings_consolidated,
    CurrencyViewSet, ExchangeRateViewSet
)

router = DefaultRouter()
router.register(r'portfolios', PortfolioViewSet, basename='portfolio')
router.register(r'categories', AssetCategoryViewSet)
router.register(r'securities', SecurityViewSet)
router.register(r'transactions', TransactionViewSet, basename='transaction')
#router.register(r'real-estate', RealEstateAssetViewSet, basename='real-estate')
router.register(r'cash-transactions', CashTransactionViewSet, basename='cash-transaction')
router.register(r'preferences', UserPreferencesViewSet, basename='preferences')
router.register(r'currencies', CurrencyViewSet)
router.register(r'exchange-rates', ExchangeRateViewSet, basename='exchangerate')

urlpatterns = [
    path('', include(router.urls)),
    path('summary/', portfolio_summary, name='portfolio-summary'),
    #path('portfolios/<int:portfolio_id>/holdings/', portfolio_holdings, name='portfolio-holdings'),
    path('portfolios/<int:portfolio_id>/consolidated/', portfolio_holdings_consolidated, name='portfolio-consolidated'),
    #path('portfolios/<int:portfolio_id>/performance/', portfolio_performance, name='portfolio-performance'),
]