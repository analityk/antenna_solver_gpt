# Model openEMS — pierwszy adapter

**Stan: implementacja eksperymentalna, bez zakończonej walidacji natywnej.**
API sprawdzono względem źródeł wydania 0.37.0-rc3. Użytkownik potwierdził
import oraz udane przygotowanie XML na Windowsie. Wykonanie FDTD
i fizyczna kontrola wyniku pozostają do sprawdzenia.

## Materiały i źródło

Odcinki osi Geometry są cylindrami PEC, ich węzły kulami o promieniu drutu.
Łączenia są ciągłe, ale nie odwzorowują dokładnie gięcia lub lutowania.
Reflektor jest skończoną płytą PEC. Otoczeniem jest próżnia.
Nie modelujemy koncentryka, baluna, wsporników, strat ani gruntu.

Port AddLumpedPort rozciąga się od x = −G/2 do +G/2, y = ±r, z = H ±r.
Jest skierowany w +x. Używa rezystancji i impedancji odniesienia 200 Ω oraz
wymuszenia impulsowego. API dodaje metalowe zakończenia portu. Przekrój jest
kwadratem o boku średnicy drutu, a nie zanikającą linią źródła.
Ta idealizacja wpływa na lokalne pole i impedancję; wymaga kontroli
przy zagęszczaniu siatki. 200 Ω nie jest wynikiem obliczenia anteny.

## Dyskretyzacja

Siatka FDTD jest kartezjańska i niejednorodna. W aktywnym obszarze krok jest
ograniczony średnicą drutu i długością fali górnej częstotliwości pasma
wymuszenia. Zachowujemy węzły, granice materiałów i portu. Poza anteną
krok rośnie z ograniczeniem growth_ratio. PML ma po 8 komórek na ścianie;
jego zewnętrzna część ma stały krok.

Domyślne 3 komórki na średnicę i 20 na długość fali są punktem startowym,
nie wykazaniem dokładności. Schodkowe odwzorowanie ukośnych przewodów i płyty
może zmieniać prądy oraz rezonans. Linie zapisują się w `mesh.npz`, ustawienia
i obwiednie w `mesh.json`. Limit max_cells odrzuca zbyt dużą siatkę;
nie szacuje zużycia pamięci ani nie obniża sam rozdzielczości.

Powierzchnia NF2FF zamyka antenę wewnątrz granic absorbujących i służy
rekonstrukcji asymptotycznego pola dalekiego. Wymuszenie jest gaussowskie;
częstotliwość środkowa i szerokość pasma są zapisane w metadanych.

## Dane i normalizacja

CalcPort zwraca transformaty sygnałów impulsowych. Zapisujemy je jako
`voltage_fourier` i `current_fourier`, nie jako nienormalizowane amplitudy
sinusoidalne w V i A. Impedancja jest ich ilorazem.

Współczynnik pola to sqrt(Pcel / Pnative) razy exp(−j arg(Vport)),
gdzie Pnative = 0,5 Re(Vport · conj(Iport)). Po jego zastosowaniu pole ma
amplitudę szczytową przy zadanej mocy przyjętej (domyślnie 1 W);
faza 0° odpowiada dodatniemu maksimum napięcia portu.
Rekonstrukcja: Re(F · exp(+j · faza)). Skończoność danych i dodatnia moc
są sprawdzane przed skalowaniem.

Promień odniesienia NF2FF to 1 m. Jest to współczynnik asymptotycznego pola,
nie twierdzenie, że 1 m leży w strefie dalekiej anteny.
Zysk odnosi się do mocy przyjętej, kierunkowość do mocy promieniowanej,
a realized gain uwzględnia 1 − |S11|² względem tego samego Zref.
Tablice zapisują wielkości liniowe; wykres ma dolny próg wyświetlania −120 dBi.

## Otwarte kontrole

Brak kontroli dipola, trzech siatek Quadosa i zakończonej walidacji portu.
Program nie potwierdza automatycznie osiągnięcia EndCriteria przed limitem
kroków; trzeba sprawdzić log. Bilans mocy PEC odbiegający o ponad 10%
generuje ostrzeżenie, ale nie zastępuje zbieżności.
Wyniki pozostają `unverified` i nie są potwierdzonym projektem wykonawczym.

Prądy, przekroje E/H i animacje nie są jeszcze zaimplementowane.
Żądanie takich danych jest odrzucane jawnie. Nie tworzymy zastępczych map.
