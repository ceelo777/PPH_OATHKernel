from django.shortcuts import render
from django.contrib.auth import models
import django.contrib.auth

def profile(request):
    user = django.contrib.auth.get_user(request)
    userList = django.contrib.auth.models.User.objects.all()
    return render(request, 'profile.html', {'user': user, 'userList': userList})

