@ECHO OFF
Rem This is a simple Windows batch script, the sole purpose of which is to
Rem indirectly create a wineserver process and keep it alive.
Rem
Rem This is necessary when running a lot of Wine commands in succession
Rem in a sandbox (eg. Steam Runtime and Winetricks), since a wineserver
Rem process is started and stopped repeatedly for each command unless one
Rem is already available.
Rem
Rem Each Steam Runtime sandbox shares the same PID namespace, meaning Wine
Rem commands in other sandboxes use it automatically without having to start
Rem their own, reducing startup time dramatically.
ECHO wineserver keepalive process started...
:LOOP
 Rem Keep this process alive until the 'keepalive' file is deleted; this is
 Rem done by Protontricks when the underlying command is finished.
 Rem
 Rem If 'restart' file appears, stop this process and wait a moment before
 Rem starting it again; this is done by the Bash script.
 Rem
 Rem Batch doesn't have a sleep command, so ping an unreachable IP with
 Rem a 2s timeout repeatedly. This is stupid, but it appears to work.
 ping 192.0.2.1 -n 1 -w 2000 >nul
 IF EXIST restart (
    ECHO stopping keepalive process temporarily...
    DEL restart
    EXIT /B 0
 )
 IF EXIST keepalive (
    goto LOOP
 ) ELSE (
    ECHO keepalive file deleted, quitting...
 )
