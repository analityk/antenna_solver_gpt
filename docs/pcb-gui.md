# PCB GUI — aplikacja okienkowa Windows

Aplikacja \`antenna_lab.pcb.gui\` jest prostym interfejsem Tkinter do **istniejących**
narzędzi \`.epro\`, openEMS i raportów. Nie implementuje drugiego solvera,
nie przepisuje fizyki, nie zmienia siatki ani nie wymaga dodatkowych bibliotek
GUI poza standardowym Pythonem z Tkinter.

## Uruchomienie

W katalogu repozytorium na Windows 11 kliknij dwukrotnie:

**\`PCB_GUI.bat\`**

lub w CMD:

\`\`\`bat
.\.venv\Scripts\python.exe -m antenna_lab.pcb.gui
\`\`\`

Jeśli okno nie otworzy się przy podwójnym kliknięciu, użyj wariantu CMD,
aby zobaczyć błąd uruchamiania; launcher korzysta z \`pythonw.exe\`
w lokalnym \`.venv\`. Dla natywnego solvera sprawdź pole
\`CSXCAD_INSTALL_PATH\` (zwykle \`C:\dev\openems\openEMS\`).

## Obsługa

1. **Wybierz projekt**: dowolne dostępne lokalnie \`.epro\`. Wybór innego
   projektu zeruje ręczny \`--source-config\` i ręczną grubość PTH,
   żeby nie przenosić założeń produkcyjnych do obcej płytki.
2. **Sprawdź projekt**: używa istniejącego
   \`antenna_lab.pcb.reduced_control --inspect-source\`, bez FAST solve,
   mesh/FDTD i bez plików Gerber. Nieznane typy rekordów CAD pozostają błędem.
3. **Ustaw eksperyment i solver**: edytuj center/cutoff, sweep od/do/co,
   częstotliwości pól E/H, profil, rozdzielczość geometrii, ewentualnie
   \`--openems-set KEY=VALUE\` (po jednej wartości w wierszu). Wszystkie
   częstotliwości z GUI są w MHz.
4. **Przygotuj siatkę**: \`--prepare-only\`; liczba komórek i audyty
   pozostają w logu oraz zapisanym \`summary.json\`. Nie uruchamia FDTD.
5. **Uruchom FDTD**: przed startem pokazuje parametry i pyta o potwierdzenie.
   Jeżeli w tej sesji GUI nie wykonano pomyślnego PREPARE-ONLY **dla dokładnie
   tych samych parametrów**, GUI ostrzega dodatkowo. Wyniki trafiają do
   katalogów \`outcomes/pcb_easyeda/<nazwa_pliku>_NNN\`, bez nadpisywania.
6. **Raport i pola**: można wskazać dowolny istniejący katalog FDTD,
   również z poprzedniej sesji. Ustaw \`active+geometry\`, próg -40 dB,
   margines 1 mm i krok fazy 15°. Raport HTML powstaje z istniejących
   CSV/NPZ, otwiera się w przeglądarce i nie uruchamia FDTD.
   Domyślnie GUI wykonuje ten krok również po pomyślnym uruchomieniu FDTD.

GUI na żywo wypisuje log, ścieżkę wyniku i pełne polecenie CMD.
Przyciskiem **Kopiuj** można je przenieść do terminala. Faktyczne
wykonanie odbywa się przez \`subprocess\` z listą argumentów i \`shell=False\`;
interfejs nie interpretuje ciągów znaków jako poleceń powłoki.

\`--source-config\` jest opcjonalny. Jeżeli nie zostanie wskazany,
istniejący importer sam rozwiązuje źródło oraz idealne wartości R/L/C
z \`.epro\` i zapisuje kontrakt w plikach wyniku. **Nie zgadujemy**
niezapisanej w CAD grubości PTH: opcjonalne pole \`PTH metalizacja\`
to jawnie podana przez użytkownika wartość w µm.

Ustawienia GUI (bez sekretów i danych wynikowych) są zachowywane lokalnie w
\`~/.antenna_lab_pcb_gui.json\`. Nie są dodawane do projektu .epro ani
do historii Git. Polecenia i rzeczywista konfiguracja FDTD pozostają
w istniejących artefaktach solvera.

## Bezpieczeństwo i ograniczenia

- GUI jest nakładką na CLI; wyłącznie jego walidacja i logika solvera
  rozstrzygają, czy projekt da się zasymulować. Samo otwarcie .epro
  nie stanowi potwierdzenia poprawnej geometrii.
- Przerwanie procesu natywnego może pozostawić niekompletne wyniki.
  GUI nie usuwa ich, nie oznacza jako \`completed\` i nie uruchamia ponownego FDTD.
- Jeden etap działa naraz. Brak sztucznego paska procentowego postępu
  FDTD: raportowane są rzeczywiste komunikaty silnika.
- Gdy brak poprawnych pól, raport nie może ich odtworzyć wyłącznie z S11.
  Weryfikuj \`stages.fields\`, \`fields/metadata.json\` i pliki NPZ.
- Domyślne wartości częstotliwości są tylko **edytowalnym przykładem**
  eksperymentu, nie są odczytane z nowego projektu CAD.
- Testy jednostkowe GUI obejmują generowanie komend bez uruchamiania
  grafiki, native FDTD ani PSU. Rzeczywista integracja z Windows i CSXCAD
  wymaga osobnego uruchomienia użytkownika.

Weryfikacja czystej warstwy komend:

\`\`\`bat
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -p test_pcb_gui_commands.py -v
\`\`\`
