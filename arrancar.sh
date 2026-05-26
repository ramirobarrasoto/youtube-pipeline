#!/bin/bash
cd ~/development/Proyectos/Youtube
source venv/bin/activate
echo "🚀 Iniciando Pipeline Maestro..."
open http://localhost:5000
venv/bin/python3 app/app.py
