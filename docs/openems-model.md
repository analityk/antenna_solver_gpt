# Model openEMS — pierwszy adapter

**Stan: implementacja eksperymentalna, bez zakończonej walidacji natywnej.**
API sprawdzono względem źródeł wydania 0.37.0-rc3. Użytkownik potwierdził
import, przygotowanie XML, FDTD i kontrolę pracy źródła na Windowsie.
Pozorny deficyt 12,15% wynika głównie z błędnego odniesienia pojedynczego U·I;
praca lokalna i strumień zewnętrzny są zgodne do 0,102%. Wariant poprawiający
wykryty błąd granic wymuszenia został wykonany natywnie: 450 dodatnich
wkładów pracy, zgodność pracy i strumienia do 0,10090%. Pojedyncze U·I
nadal zawyża odniesienie; kontrola portu pozostaje otwarta.

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

Siatka zaokrągla kotwice do 12 miejsc po przecinku w metrach. Przekazanie
do AddLumpedPort niezaokrąglonych granic wyklucza w pierwszym modelu dwie
warstwy wymuszenia: opór jest przyciągany do siatki i obejmuje 450 krawędzi,
a źródło korzysta z testu punkt-wewnątrz-boxa i obejmuje tylko 270.
`solver.port_mesh_alignment=mesh_anchors` przekazuje dokładne istniejące
kotwice do całego portu. Dopuszcza odchyłkę najwyżej 1e-12 m, zapisuje audyt
i odrzuca większą niezgodność. Geometria anteny i siatka pozostają bez zmian.
Brak opcji lub `legacy` odtwarza stare granice i zgłasza niepełne pokrycie.
To zgodność wsteczna do porównań, nie zalecany poprawiony model.
Konfiguracja kontrolna: `parameters/quados8_1420mhz_aligned_feed.json`.
Jej wynik przy 1420 MHz: lokalna praca 0,949145539 W przy odczycie portu 1 W.
Amplitudy 25 linii U różnią się nadal do 9,897%, fazy do 4,281°. Pełne
pokrycie boxem nie zapewniło poprawnego pomiaru mocy przez jedną linię U
i jeden przekrój I. Z i SWR pozostają wynikami konkretnego modelu zasilania,
przed kontrolą bardziej lokalnego źródła i zbieżności.

## Dyskretyzacja

Siatka FDTD jest kartezjańska i niejednorodna. W aktywnym obszarze krok jest
ograniczony średnicą drutu i długością fali górnej częstotliwości pasma
wymuszenia. Zachowujemy węzły, granice materiałów i portu. Poza anteną
krok rośnie z ograniczeniem growth_ratio wewnątrz dodawanego otoczenia;
znane naruszenie limitu na połączeniach przedziałów opisano niżej.
PML ma po 8 komórek na ścianie;
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
amplitudę szczytową przy zadanym odniesieniu pomiaru portu (domyślnie 1 W);
faza 0° odpowiada dodatniemu maksimum napięcia portu.
Rekonstrukcja: Re(F · exp(+j · faza)). Skończoność danych i dodatnia moc
są sprawdzane przed skalowaniem.
Wynik source_work wykazał, że w starym modelu ta wielkość nie równa się
lokalnej pracy netto. Nazwa `accepted_power_w` pozostaje w kontrakcie v2,
ale nie potwierdza poprawności pomiaru mocy ani zysku. Nie przepisano starych
wyników i nie dopasowano normalizacji do strumienia NF2FF.

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

Przed skalowaniem aktywny jest plan [diagnostyki mocy](power-audit.md).
Opcjonalne monitory nie zmieniają geometrii ani siatki; zapisują trzy strumienie
i profile U/I portu. Znany skok rozmiaru komórek do 1,8667 pozostaje w tym
wariancie kontrolnym; `growth_ratio` obecnie nie gwarantuje globalnego limitu.
Brak którejkolwiek z sześciu par plików NF2FF jest teraz jawnym błędem.

Przekroje E/H zapisują pasywne dumpy FD 10/11, z interpolacją do wspólnych
węzłów (dump_mode=1). Faza H uwzględnia natywne znaczniki czasu; nie dodajemy
drugiej korekty półkroku. Normalizacja jest taka sama jak w port_spectra.npz.
Maska obejmuje PEC, lokalną przekątną komórki wokół niego oraz port z otoczeniem.
Położenia są przyciągane do istniejącej siatki i jawnie zapisane. Szczegóły,
kontrakt pól oraz ograniczenia: [fields.md](fields.md). Natywna kontrola
nowych przekrojów pozostaje otwarta. Prądy i pełna animacja są odrzucane.
