# Aplikacja lokalna

Polecenie preview otwiera formularz Tk/ttk z podglądem Matplotlib.
Pola obsługują zwykłe wpisywanie, wklejanie i Tab bez rysowania figury.
Enter lub Zastosuj zatwierdza komplet zmian; niepoprawne dane nie zastępują
ostatniej poprawnej konfiguracji. Zmiana częstotliwości i skalowanie są odrębne.

- Wczytaj parametry: wybór JSON, walidacja i odświeżenie pól oraz podglądu.
  Wczytany wariant zastępuje bieżące pola i staje się punktem przywracania.
  Anulowanie lub błędny plik zachowuje dotychczasowe ustawienia i wpisy.
  Nazwa wybranego pliku służy także jako etykieta kolejnego eksportu geometrii.
  Można przełączać modele Quados 8 i biquad; pola wymiarów zmieniają się automatycznie.
- Zapisz parametry (.json): jeden plik ustawień do ponownego wczytania lub użycia przez --config.
- Eksportuj geometrię: nowy folder z modelem, PNG, parametrami i dokumentacją.
  Eksport nie uruchamia openEMS. Zapis i eksport uwzględniają niezastosowane pola.

EditorState zawiera logikę zatwierdzania niezależną od kontrolek GUI.
GeometryEditor łączy ją z Tk. tkinter jest częścią standardowej instalacji
Pythona dla Windows; nie dodajemy nowej zależności pip.
Porównania wariantów, serie i przegląd pól pozostają do implementacji.
