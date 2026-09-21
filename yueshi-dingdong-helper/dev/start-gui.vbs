' Yueshi Dingdong helper - silent GUI launcher (no console window)
' Build venv lives in %LOCALAPPDATA%\YueshiDingdongHelper\build-venv.
Set fso = CreateObject("Scripting.FileSystemObject")
Set ws = CreateObject("WScript.Shell")
devDir = fso.GetParentFolderName(WScript.ScriptFullName)
ws.CurrentDirectory = fso.GetParentFolderName(devDir)
venvPy = ws.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\YueshiDingdongHelper\build-venv\Scripts\pythonw.exe"
If fso.FileExists(venvPy) Then
    ws.Run """" & venvPy & """ src\gui.py", 0, False
Else
    ws.Run "pythonw src\gui.py", 0, False
End If
