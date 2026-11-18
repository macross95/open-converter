; Instalador de Open Converter (requiere Inno Setup 6.5 o superior).
;
; Compilar:  "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" installer.iss
; Antes:     python -m PyInstaller "Open Converter.spec" --noconfirm --clean
; Imágenes:  python installer\make_art.py  (solo si cambian los colores o el logo)

#define MyAppName "Open Converter"
#define MyAppVersion "0.4.0"
#define MyAppPublisher "MacrosS"
#define MyAppExeName "Open Converter.exe"
#define MyAppDist "dist\Open Converter"

[Setup]
; No cambiar AppId: Windows reconoce las instalaciones existentes por este valor exacto.
AppId={{B2C3D4E5-F6A7-8901-BCDE-F12345678901}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={sd}\OpenConverter\Open Converter
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableWelcomePage=no
OutputDir=installer_output
OutputBaseFilename=Open Converter-Setup-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Instalador de {#MyAppName}

; Diseño del programa: tema oscuro azul, fondo con degradado y logo
WizardStyle=modern dark polar includetitlebar hidebevels
WizardBackColor=#0b1020
WizardBackImageFile=installer\art\background.png
WizardImageFile=installer\art\side_202.png,installer\art\side_336.png,installer\art\side_430.png
WizardSmallImageFile=installer\art\small_55.png,installer\art\small_83.png,installer\art\small_110.png

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
spanish.DrivePageTitle=Disco de instalación
spanish.DrivePageDescription=Elige el disco donde se instalará {#MyAppName}.
spanish.DrivePageLabel=Discos disponibles:
english.DrivePageTitle=Installation drive
english.DrivePageDescription=Choose the drive where {#MyAppName} will be installed.
english.DrivePageLabel=Available drives:

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MyAppDist}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\_internal\assets\icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\_internal\assets\icon.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
const
  BM_CLICK = $00F5;

var
  DrivePage: TInputOptionWizardPage;
  DriveLetters: array of String;
  Overlays: array[0..2] of TBitmapButton;  { 0 = Siguiente, 1 = Atrás, 2 = Cancelar }

function GetLogicalDrives: DWORD; external 'GetLogicalDrives@kernel32.dll stdcall';

{ ---------- Botones con degradado ----------
  Cada botón real del asistente queda debajo de un TBitmapButton dibujado con degradado.
  El clic se reenvía al botón real (BM_CLICK), así funcionan Enter, Esc, Alt+letra,
  las validaciones y el cambio de página como siempre. }

function RGBColor(R, G, B: Integer): TColor;
begin
  Result := R or (G shl 8) or (B shl 16);
end;

function Mix(A, B: Integer; T: Extended): Integer;
begin
  Result := A + Round((B - A) * T);
end;

function TargetButton(Index: Integer): TNewButton;
begin
  case Index of
    0: Result := WizardForm.NextButton;
    1: Result := WizardForm.BackButton;
  else
    Result := WizardForm.CancelButton;
  end;
end;

{ Botones con el estilo actual del programa:
  - Principal (Siguiente/Instalar/Finalizar): degradado diagonal azul -> índigo, línea de luz
    sutil arriba y un resplandor azul bajo el botón.
  - Secundarios (Atrás/Cancelar): vidrio translúcido sobre el fondo con borde fino de luz. }
procedure PaintModernButton(Btn: TBitmapButton; Caption: String; Primary: Boolean);
var
  Bmp: TBitmap;
  W, H, BH, X, Y, Radius, TX, TY: Integer;
  T, Cover, DX, DY, D2, Inner, Outer, Edge, A, Fill, Stroke: Extended;
  R, G, B: Integer;
  IsBorder: Boolean;
begin
  W := Btn.Width - 4;   { TBitmapButton deja 2 px de margen alrededor de la imagen }
  H := Btn.Height - 4;
  if (W < 8) or (H < 10) then
    Exit;
  BH := H - 2;   { las 2 filas de abajo son el resplandor }
  Radius := BH div 3;
  Inner := (Radius - 0.5) * (Radius - 0.5);
  Outer := (Radius + 0.5) * (Radius + 0.5);
  Edge := (Radius - 1.5) * (Radius - 1.5);
  Bmp := TBitmap.Create;
  try
    Bmp.Width := W;
    Bmp.Height := H;
    for Y := 0 to H - 1 do
      for X := 0 to W - 1 do
      begin
        if Y >= BH then
        begin
          { Resplandor azul bajo el botón principal; los secundarios no brillan }
          A := 0;
          if Primary and (X >= Radius) and (X < W - Radius) then
            A := 0.38 - 0.22 * (Y - BH);
          Bmp.Canvas.Pixels[X, Y] := RGBColor(Mix(11, 59, A), Mix(16, 110, A), Mix(32, 246, A));
          Continue;
        end;
        Cover := 1;
        DX := 0;
        DY := 0;
        if X < Radius then DX := Radius - (X + 0.5)
        else if X >= W - Radius then DX := (X + 0.5) - (W - Radius);
        if Y < Radius then DY := Radius - (Y + 0.5)
        else if Y >= BH - Radius then DY := (Y + 0.5) - (BH - Radius);
        IsBorder := (X = 0) or (X = W - 1) or (Y = 0) or (Y = BH - 1);
        if (DX > 0) and (DY > 0) then
        begin
          D2 := DX * DX + DY * DY;
          if D2 >= Outer then Cover := 0
          else if D2 > Inner then Cover := (Outer - D2) / (Outer - Inner);
          IsBorder := D2 > Edge;
        end;
        { X * 1.0: en Pascal Script la división entre enteros es entera }
        if Primary then
        begin
          T := ((X * 1.0) / (W - 1)) * 0.65 + ((Y * 1.0) / (BH - 1)) * 0.35;
          if T < 0.5 then
          begin
            R := Mix(56, 37, T * 2); G := Mix(148, 99, T * 2); B := Mix(255, 235, T * 2);
          end
          else
          begin
            R := Mix(37, 99, (T - 0.5) * 2); G := Mix(99, 88, (T - 0.5) * 2); B := Mix(235, 240, (T - 0.5) * 2);
          end;
          if IsBorder and (Y < BH div 2) then  { línea de luz sutil arriba }
          begin
            A := 0.32 * (1 - (Y * 2.0) / BH);
            R := Mix(R, 255, A); G := Mix(G, 255, A); B := Mix(B, 255, A);
          end;
        end
        else
        begin
          { Vidrio: blanco translúcido sobre el fondo #0b1020, más claro arriba }
          Fill := 0.094 - 0.059 * ((Y * 1.0) / (BH - 1));
          Stroke := 0.20 - 0.15 * ((Y * 1.0) / (BH - 1));
          if IsBorder then A := Stroke else A := Fill;
          R := Mix(11, 255, A); G := Mix(16, 255, A); B := Mix(32, 255, A);
        end;
        Bmp.Canvas.Pixels[X, Y] := RGBColor(Mix(11, R, Cover), Mix(16, G, Cover), Mix(32, B, Cover));
      end;
    Bmp.Canvas.Brush.Style := bsClear;
    Bmp.Canvas.Font.Name := 'Segoe UI Semibold';
    Bmp.Canvas.Font.Height := -ScaleY(12);
    if Primary then
      Bmp.Canvas.Font.Color := clWhite
    else
      Bmp.Canvas.Font.Color := RGBColor(241, 245, 249);
    TX := (W - Bmp.Canvas.TextWidth(Caption)) div 2;
    TY := (BH - Bmp.Canvas.TextHeight(Caption)) div 2;
    Bmp.Canvas.TextOut(TX, TY, Caption);
    Btn.Bitmap := Bmp;
  finally
    Bmp.Free;
  end;
end;

procedure OverlayClick(Sender: TObject);
var
  I: Integer;
begin
  for I := 0 to 2 do
    if Sender = Overlays[I] then
      PostMessage(TargetButton(I).Handle, BM_CLICK, 0, 0);
end;

procedure SyncOverlays;
var
  I: Integer;
  Real: TNewButton;
  Caption: String;
begin
  for I := 0 to 2 do
  begin
    Real := TargetButton(I);
    Overlays[I].Left := Real.Left;
    Overlays[I].Top := Real.Top;
    Overlays[I].Width := Real.Width;
    Overlays[I].Height := Real.Height;
    Overlays[I].Visible := Real.Visible and Real.Enabled;
    if Overlays[I].Visible then
    begin
      Caption := Real.Caption;
      StringChangeEx(Caption, '&', '', True);
      Overlays[I].Caption := Caption;  { para lectores de pantalla }
      { Siguiente/Instalar/Finalizar con degradado, como Convertir; Atrás y Cancelar en vidrio }
      PaintModernButton(Overlays[I], Caption, I = 0);
      Real.SendToBack;
      Overlays[I].BringToFront;
    end;
  end;
end;

{ ---------- Página para elegir el disco ---------- }

procedure InitializeWizard;
var
  Mask: DWORD;
  I, Idx: Integer;
  Letter: String;
begin
  Mask := GetLogicalDrives();
  Idx := 0;
  for I := 0 to 25 do
  begin
    if (Mask and (1 shl I)) <> 0 then
    begin
      Letter := Chr(Ord('A') + I) + ':\';
      if DirExists(Letter) then  { solo discos disponibles }
      begin
        SetArrayLength(DriveLetters, Idx + 1);
        DriveLetters[Idx] := Letter;
        Idx := Idx + 1;
      end;
    end;
  end;
  DrivePage := CreateInputOptionPage(wpWelcome, CustomMessage('DrivePageTitle'),
    CustomMessage('DrivePageDescription'), CustomMessage('DrivePageLabel'), True, False);
  for I := 0 to GetArrayLength(DriveLetters) - 1 do
    DrivePage.Add(DriveLetters[I]);
  if GetArrayLength(DriveLetters) > 0 then
    DrivePage.SelectedValueIndex := 0;

  for I := 0 to 2 do
  begin
    Overlays[I] := TBitmapButton.Create(WizardForm);
    Overlays[I].Parent := TargetButton(I).Parent;
    Overlays[I].BackColor := RGBColor(11, 16, 32);
    Overlays[I].Cursor := crHand;
    Overlays[I].OnClick := @OverlayClick;
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = wpSelectDir) and (ExpandConstant('{param:DIR}') = '') then
  begin
    if GetArrayLength(DriveLetters) > 0 then
      WizardForm.DirEdit.Text := DriveLetters[DrivePage.SelectedValueIndex] + 'OpenConverter\Open Converter';
  end;
  SyncOverlays;
end;
