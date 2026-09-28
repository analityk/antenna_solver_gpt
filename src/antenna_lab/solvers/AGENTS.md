# Adaptery solverów

Wybrany solver: openEMS 0.37.0rc3. Kod adaptera istnieje; natywna integracja
i poprawność fizyczna wymagają sprawdzenia na Windowsie. Wyniki są unverified.

- Importy openEMS i CSXCAD pozostają tutaj i są opóźnione do przygotowania modelu.
- Modeluj cylindry ze złączami, skończoną płytę PEC i port opisany w
  `docs/openems-model.md`. Nie zastępuj po cichu płyty siatką przewodów.
- Zapisuj pełne FDTD XML, linie siatki, wersje, ustawienia i komunikaty solvera.
- Zachowuj węzły portu i obszar PML. Przekroczenie limitu komórek jest błędem,
  nie powodem do cichego pogorszenia rozdzielczości.
- Sprawdzaj częstotliwości, skończoność danych i dodatnią moc przed normalizacją.
- Surowe widma impulsowego portu nie są zwykłymi amplitudami napięcia/prądu.
  Zachowuj je osobno; normalizuj fazory pola do mocy i fazy portu.
- Nie utożsamiaj zakończenia Run z osiągnięciem EndCriteria lub zbieżnością.
- Nie zgłaszaj obsługi prądów, E/H, baluna lub dielektryków przez ich pominięcie.
- API porównuj z przypiętymi źródłami w `docs/sources.md`; nie zgaduj sygnatur.
