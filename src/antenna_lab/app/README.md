# Aplikacja lokalna

Polecenie preview otwiera formularz Tk/ttk z podglądem Matplotlib.
Pola obsługują zwykłe wpisywanie, wklejanie i Tab bez rysowania figury.
Enter lub Zastosuj zatwierdza komplet zmian; niepoprawne dane nie zastępują
ostatniej poprawnej konfiguracji. Zmiana częstotliwości i skalowanie są odrębne.

- Zapisz parametry (.json): jeden plik ustawień do ponownego użycia przez --config.
- Eksportuj geometrię: nowy folder z modelem, PNG, parametrami i dokumentacją.
  Eksport nie uruchamia openEMS. Obie akcje uwzględniają niezastosowane pola.

EditorState zawiera logikę zatwierdzania niezależną od kontrolek GUI.
GeometryEditor łączy ją z Tk. tkinter jest częścią standardowej instalacji
Pythona dla Windows; nie dodajemy nowej zależności pip.
Porównania wariantów, serie i przegląd pól pozostają do implementacji.
