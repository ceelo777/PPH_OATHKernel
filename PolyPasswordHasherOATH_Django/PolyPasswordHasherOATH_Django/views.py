from django.shortcuts import render
import django.contrib.auth
from django.utils.crypto import get_random_string
from django.http import HttpResponseRedirect
from django.contrib.auth import authenticate
from django.contrib.auth import login as realLogin
from django.contrib.auth.models import User
from django.contrib.auth import hashers

def profile(request):
    user = django.contrib.auth.get_user(request)
    userList = django.contrib.auth.models.User.objects.all()
    return render(request, 'profile.html', {'user': user, 'userList': userList})

def login(request):
    username = request.POST['username']
    try:
        user = User.objects.get(username=username)
        algorithm, sharenumber, iterations, salt, challenge, XORresponse = user.password.split('$', 5)
        return render(request, 'yubikey.html', {"username": username, "challenge": challenge} )
    except:
        return HttpResponseRedirect("/login/")

def deleteAccount(request):
    account = request.POST['delete']
    try:
        user = User.objects.get(username=account)
        user.delete()
        return HttpResponseRedirect("/accounts/profile")
    except:
        return HttpResponseRedirect("/accounts/profile")

def yubikeyAuth(request):
    username = request.POST['username']
    password = request.POST['password']
    challenge = request.POST['oath_challenge']
    response = request.POST['oath_resp']
    pph = hashers.get_hasher()
    user = authenticate(username=username, password=password+'\x00'+challenge+'\x00'+response)
    if user is not None:
        realLogin(request, user)
    else:
        return HttpResponseRedirect("/login/")
    return HttpResponseRedirect("/accounts/profile")
        

def register(request):
    username = request.POST['username']
    password = request.POST['password'].encode("ascii")
    challenge = request.POST['oath_challenge'].encode("ascii")
    response = request.POST['oath_resp'].encode("ascii")
    try:
        user = User.objects.get(username=username)
        return HttpResponseRedirect("/register")
    except:
        user = User()
        user.username = username
        salt = get_random_string(8)
        pph = hashers.get_hasher()
        password = password+'\x00'+challenge+'\x00'+response
        user.password = pph.encode(password, "$"+salt)
        user.save()
        return HttpResponseRedirect("/login/")
        
def show_login(request):        
    return render(request, 'login.html')

def show_register(request):
    challenge = get_random_string(8)
    return render(request, 'register.html', {"challenge": challenge})
