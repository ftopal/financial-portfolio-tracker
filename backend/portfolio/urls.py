from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'portfolios', views.PortfolioViewSet, basename='portfolio')
router.register(r'securities', views.SecurityViewSet, basename='security')
router.register(r'transactions', views.TransactionViewSet, basename='transaction')
router.register(r'categories', views.AssetCategoryViewSet, basename='category')

urlpatterns = [
    path('', include(router.urls)),
    path('summary/', views.portfolio_summary, name='portfolio-summary'),
    path('portfolios/<int:portfolio_id>/holdings-consolidated/',
         views.portfolio_holdings_consolidated, name='portfolio-holdings-consolidated'),
]