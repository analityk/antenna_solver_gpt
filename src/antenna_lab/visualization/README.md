# Wizualizacja

Dostępne: dwa rzuty geometrii, wykres impedancji, przekroje pola dalekiego
oraz raport HTML. Wykresy elektromagnetyczne powstają wyłącznie z zapisanych
danych CSV/NPZ po obliczeniu, z oznaczeniem unverified.

`report_data.py` odczytuje wyniki, a `report.py` tworzy samodzielny HTML.
`report_assets.py` zawiera CSS/JS, bez bibliotek sieciowych. Suwak, Zref,
kliknięcie wykresu, minimum SWR i CSV działają w lokalnej przeglądarce.
Matplotlib tworzy obrazy pola dalekiego i statyczny wykres widma do wydruku.
`report --latest --open` zapisuje nowy plik poza niezmiennym przebiegiem;
raport automatyczny powstaje przed końcowym manifestem nowego `run`.
Opcjonalna DFT używa istniejących próbek portu, bez natywnego solvera.
Opis zakresu, braków danych i interpretacji: `docs/reports.md`.

Pola bliskie i animacje są planowane w M3. Będą korzystać z zespolonych danych,
jawnych masek i wspólnych skal; zmiana fazy nie może uruchamiać solvera.
Interpolacja obrazu nie oznacza gęstszej siatki obliczeniowej.
