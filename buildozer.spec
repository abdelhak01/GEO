[app]
title = GEO
package.name = ateliervitrage
package.domain = org.atelier

source.dir = .
source.include_exts = py

version = 1.0

requirements = python3==3.11.9,hostpython3==3.11.9,kivy

orientation = landscape
fullscreen = 0

android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE

android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1
