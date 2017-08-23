from django.shortcuts import render
import django.contrib.auth
from django.utils.crypto import get_random_string
from django.http import HttpResponseRedirect
from django.contrib.auth import authenticate
from django.contrib.auth import login as realLogin
from django.contrib.auth.models import User

def profile(request):
    user = django.contrib.auth.get_user(request)
    userList = django.contrib.auth.models.User.objects.all()
    return render(request, 'profile.html', {'user': user, 'userList': userList})

def login(request):
    #import pdb; pdb.set_trace()
    username = request.POST['username']
    #password = request.POST['password']
    #challenge = request.POST['oath_challenge']
    #response = request.POST['oath_resp']
    #user = authenticate(request, username=username)#, password=password)#+'\x00'+challenge+'\x00'+response)
    try:
        User.objects.get(username=username)
        return render(request, 'yubikey.html', {"username": username})
    #return HttpResponseRedirect("/yubiAuth/")
    except:
        return HttpResponseRedirect("/login/")
    
    if (user !=None):
        #import bpdb; bpdb.set_trace()
        #realLogin(request, user)
        #return HttpResponseRedirect("/accounts/profile/")
        return HttpResponseRedirect("/yubiAuth/")
    else:
        return HttpResponseRedirect("/login/")

def yubikeyAuth(request):
    username = request.POST['username']
    password = request.POST['password']
    response = request.POST['oath_resp']

def register(request):
    username = request.POST['username']
    password = request.POST['password']
    challenge = request.POST['oath_challenge']
    response = request.POST['oath_resp']
    # Check if username already exists
    try:
        user = User.objects.get(username=username)
        return HttpResponseRedirect("/register")
    except:
        user = User()
        user.username = username
        user.set_password(password+'\x00'+challenge+'\x00'+response)
        user.save()
        return HttpResponseRedirect("/login/")
        
def show_login(request):        
    return render(request, 'login.html')#, {"challenge": challenge})

def show_register(request):
    challenge = get_random_string(8)
    return render(request, 'register.html', {"challenge": challenge})
