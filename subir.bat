@echo off
chcp 65001 >nul
title FLOW - subindo o sistema
cd /d "%~dp0"

echo ==========================================
echo   FLOW - subindo API, pagamentos e web
echo ==========================================
echo.

rem 1) arquivos antigos: as telas sairam da API e foram para o projeto WEB
for %%f in (pagamentos.py views.py forms.py urls.py context_processors.py pagamentos_client.py) do (
    if exist "FLUXO_APROVACAO\SISTEMA\%%f" (
        del "FLUXO_APROVACAO\SISTEMA\%%f"
        echo [ok] Removido FLUXO_APROVACAO\SISTEMA\%%f ^(versao antiga^)
    )
)
if exist "FLUXO_APROVACAO\SISTEMA\templates" (
    rmdir /s /q "FLUXO_APROVACAO\SISTEMA\templates"
    echo [ok] Removida a pasta FLUXO_APROVACAO\SISTEMA\templates ^(as telas agora estao em WEB^)
)
if exist "FLUXO_APROVACAO\static" (
    rmdir /s /q "FLUXO_APROVACAO\static"
    echo [ok] Removida a pasta FLUXO_APROVACAO\static ^(agora em WEB\static^)
)

rem 2) .env
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo [ok] .env criado a partir do .env.example
)

rem 3) Docker Desktop precisa estar aberto
docker info >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERRO] O Docker Desktop nao esta rodando.
    echo        Abra o Docker Desktop, espere aparecer "Engine running" e rode este arquivo de novo.
    echo.
    pause
    exit /b 1
)
echo [ok] Docker rodando

rem 4) derruba a versao anterior e libera a porta 8000
docker compose down --remove-orphans >nul 2>&1

for /f "delims=" %%c in ('docker ps -q --filter "publish=8000"') do (
    echo [aviso] Um container de outro projeto esta usando a porta 8000:
    docker ps --filter "id=%%c" --format "         {{.Names}} ({{.Image}})"
    echo         Parando esse container...
    docker stop %%c >nul
)

set "PID8000="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:":8000 .*LISTENING"') do set "PID8000=%%p"
if defined PID8000 (
    for /f "tokens=1" %%n in ('tasklist /fi "pid eq %PID8000%" /nh') do set "PROG8000=%%n"
)
if defined PID8000 (
    echo %PROG8000% | findstr /i "docker wslrelay vpnkit" >nul
    if not errorlevel 1 (
        echo.
        echo [ERRO] A porta 8000 esta presa pelo proprio Docker ^(%PROG8000%^).
        echo        Reinicie o Docker Desktop ^(icone da baleia ^> Restart^) e rode este arquivo de novo.
        pause
        exit /b 1
    )
)
if defined PID8000 (
    echo.
    echo [aviso] A porta 8000 esta sendo usada pelo programa: %PROG8000% ^(PID %PID8000%^)
    echo         Normalmente e um "python manage.py runserver" esquecido aberto.
    choice /c SN /m "         Encerrar esse programa agora"
    if errorlevel 2 (
        echo Feche o programa que usa a porta 8000 e rode este arquivo de novo.
        pause
        exit /b 1
    )
    taskkill /pid %PID8000% /f >nul
    timeout /t 2 /nobreak >nul
    echo [ok] Porta 8000 liberada
)

rem 5) sobe tudo (o banco e preservado; as migracoes rodam sozinhas)
echo.
echo Construindo e subindo os containers (a primeira vez demora alguns minutos)...
docker compose up -d --build
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao subir os containers. Veja as mensagens acima.
    pause
    exit /b 1
)

rem 6) espera o sistema responder
echo.
echo Aguardando o sistema ficar pronto...
set /a tentativas=0
:esperar
set /a tentativas+=1
curl -s -o nul -w "%%{http_code}" http://localhost:8000/api/v1/schema/ | findstr "200" >nul
if errorlevel 1 goto aguardar
curl -s -o nul -w "%%{http_code}" http://localhost:8000/login/ | findstr "200" >nul
if not errorlevel 1 goto pronto
:aguardar
if %tentativas% geq 60 (
    echo [ERRO] O sistema nao respondeu em 3 minutos.
    echo        Rode:  docker compose logs api frontend   e mande o resultado.
    pause
    exit /b 1
)
timeout /t 3 /nobreak >nul
goto esperar

:pronto
echo [ok] Sistema no ar

rem 7) dados de teste
echo.
docker compose exec -T api python manage.py popular_demo

echo.
docker compose ps
echo.
echo ==========================================
echo   Pronto!
echo.
echo   Sistema web ........ http://localhost:8000   (front: so telas, dados via API)
echo   Swagger API ........ http://localhost:8000/api/v1/docs/
echo   Swagger Pagamentos . http://localhost:8000/api/pagamentos/docs/
echo   E-mails (Mailpit) .. http://localhost:8025
echo   RabbitMQ ........... http://localhost:15672   (flow / flow)
echo.
echo   Login: demo.admin / Flow@2026
echo ==========================================
start "" http://localhost:8000
start "" http://localhost:8025
echo.
pause
