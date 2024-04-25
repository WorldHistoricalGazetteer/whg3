from django.urls import path
from . import views
from django.contrib.auth.views import * 

app_name = "accounts"

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    # path('profile/', views.update_profile, name='profile'),
    path('confirm_email/<str:token>/', views.confirm_email, name='confirm-email'),
    path('confirmation_sent/', views.confirmation_sent, name='confirmation-sent'),
    path('confirmation_success/', views.confirmation_success, name='confirmation-success'),


    path('password_reset/', PasswordResetView.as_view(template_name='registration/password_reset_form.html'),
         name='password_reset'),
    path('password_reset/done/', PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'),
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/', PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'),
         name='password_reset_confirm'),
    path('reset/done/', PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'),
         name='password_reset_complete'),
    path('password_change/', PasswordChangeView.as_view(template_name='registration/password_change_form.html'),
         name='password_change'),
    path('password_change/done/',
         PasswordChangeDoneView.as_view(template_name='registration/password_change_form.html'),
         name='password_change_done'),

]
