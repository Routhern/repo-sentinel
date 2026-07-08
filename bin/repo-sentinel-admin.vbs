' 관리자 권한으로 repo-sentinel을 실행한다.
' Windows에서 심볼릭 링크 생성(pick/relink)은 개발자 모드가 꺼져 있으면
' 관리자 권한이 필요하다 (CLAUDE.md 참고). 이 스크립트는 UAC 승인만으로
' 별도 설치 없이 상승 권한 프로세스를 띄우는 용도다.
'
' 사용법: 더블클릭하면 TUI(tui)를 관리자 권한으로 실행한다.
'        인자를 주면 그대로 CLI에 전달한다. 예:
'        wscript bin\repo-sentinel-admin.vbs pick myrepo .env

Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
repoRoot = fso.GetParentFolderName(scriptDir)

args = ""
For i = 0 To WScript.Arguments.Count - 1
    args = args & " " & Chr(34) & WScript.Arguments(i) & Chr(34)
Next
If args = "" Then args = " tui"

command = "/c cd /d " & Chr(34) & repoRoot & Chr(34) & _
    " && uv run repo-sentinel" & args & " & pause"

Set objShell = CreateObject("Shell.Application")
objShell.ShellExecute "cmd.exe", command, "", "runas", 1
