from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .forms import LoginForm
from .models import User

def login_view(request):
    form = LoginForm(request.POST or None)
    msg = None

    if request.method == "POST":
        if form.is_valid():
            email = form.cleaned_data.get("email")
            password = form.cleaned_data.get("password")
            user = authenticate(email=email, password=password)

            if user is not None:
                login(request, user)

                if user.role == "HRD":
                    return redirect("/hrd/")
                elif user.role == "Karyawan Tetap":
                    return redirect("karyawan_dashboard")
                elif user.role in ["Magang", "Part Time", "Freelance", "Project"]:
                    return redirect("magang_dashboard")
                else:
                    msg = "Role tidak valid!"
            else:
                msg = "Email atau password salah!"
        else:
            msg = "Form tidak valid!"

    return render(request, "authentication/login.html", {"form": form, "msg": msg})

@login_required
def logout_view(request):
    logout(request)
    return redirect("/")
