@echo off
chcp 65001 >nul
cd /d "D:\blender\自制插件调试\E_Tools_Extensions\Extensions\ricci_uv\native\build"
cmake --build . --config Release
pause
