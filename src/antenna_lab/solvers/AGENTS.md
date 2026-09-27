# Adaptery solverów

Implementacja NEC2++: etap M2, jeszcze nie wykonana.

- Tylko tutaj przeliczaj Hz na jednostki API solvera.
- Zapisuj wersję, ustawienia dyskretyzacji, plik wejściowy i komunikaty solvera.
- Sprawdzaj potwierdzoną częstotliwość, skończoność wyników i dodatnią moc
  przed normalizowaniem do 1 W.
- Nie używaj automatycznie rozszerzonego jądra cienkoprzewodowego:
  wcześniejszy eksperyment PyNEC 2.3.4 pokazał problemy z polem E.
  Zmiana wymaga osobnej kontroli fizycznej i wpisu w historii.
- Nie zgłaszaj obsługi ciągłej blachy, baluna lub dielektryka poprzez
  zignorowanie tych elementów. Każde przybliżenie jest częścią wyniku.

