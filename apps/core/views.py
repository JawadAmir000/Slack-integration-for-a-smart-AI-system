from django.shortcuts import render
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import SlackWorkspace, SlackUser, SlackAppConfiguration


class HomeView(TemplateView):
    """
    Home page view with Slack integration form
    """
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Slack Integration App'
        return context


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Dashboard view for authenticated users
    """
    template_name = 'core/dashboard.html'
    login_url = '/admin/login/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Dashboard'
        
        # Get user's connected Slack workspaces
        if self.request.user.is_authenticated:
            slack_users = SlackUser.objects.filter(
                user=self.request.user, 
                is_active=True
            ).select_related('workspace')
            context['connected_workspaces'] = slack_users
        
        return context


class ConfigManagementView(UserPassesTestMixin, TemplateView):
    """
    Configuration management view for admin users
    """
    template_name = 'core/config_management.html'
    login_url = '/admin/login/'

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Slack Configuration Management'
        return context


class HealthCheckView(APIView):
    """
    Simple health check endpoint
    """
    def get(self, request):
        return Response({
            'status': 'healthy',
            'message': 'Slack Integration API is running'
        }, status=status.HTTP_200_OK)