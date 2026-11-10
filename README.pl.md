# Temporary Access dla Home Assistanta

*[English version](README.md)*

Integracja pozwala wysłać gościowi link z PIN-em, którym przez określony czas może sterować wybranymi encjami: światłem, bramą, furtką, roletą. Home Assistant nie jest wystawiony do internetu. Sam łączy się z portalem przez WebSocket i sam sprawdza każde polecenie gościa przed wykonaniem.

Do działania potrzebny jest portal ([ha-access-portal](https://github.com/pgpotasiak/ha-access-portal)) i jednorazowy kod zaproszenia od jego administratora.

Wymaga Home Assistanta 2025.6 lub nowszego. Licencja MIT.

## Instalacja

**Przez HACS** (zalecane, aktualizacje jednym kliknięciem): HACS → menu ⋮ → *Niestandardowe repozytoria* → `https://github.com/pgpotasiak/ha-access-integration`, typ *Integracja*. Potem wyszukaj *Temporary Access*, pobierz i zrestartuj Home Assistanta.

**Ręcznie:** skopiuj folder `custom_components/temp_access` do folderu `/config/custom_components/` w Home Assistancie (np. dodatkiem Studio Code Server albo przez udział Samba). Zrestartuj Home Assistanta.

## Konfiguracja

*Ustawienia → Urządzenia i usługi → Dodaj integrację → Temporary Access.* Podaj adres portalu, kod zaproszenia i nazwę domu. Po chwili encja **Połączenie z portalem** powinna pokazać stan *Połączono*.

## Strona „Dostęp gości” w menu bocznym

Integracja dodaje do lewego menu HA pozycję **Dostęp gości** (widoczną tylko dla administratorów). Na tej stronie:

- widzisz wszystkie panele: status, czas do końca, kontrolki z liczbą użyć, ostatnią akcję gościa i błędne PIN-y,
- przy każdym panelu: pokaż kod QR, kopiuj link, pokaż i kopiuj PIN, unieważnij, usuń,
- przycisk **Nowy panel** otwiera formularz na tej samej stronie, a po utworzeniu od razu pokazuje link, PIN i kod QR.

## Tworzenie panelu w ustawieniach integracji

*Ustawienia → Urządzenia i usługi → Temporary Access* → przycisk **Dodaj panel gościa** (przy wpisie integracji, menu ⋮ albo przycisk na górze listy wpisów).

1. Pierwszy krok: tytuł, encje dla gościa, czas trwania, opcjonalnie początek dostępu, dni tygodnia, godziny i PIN.
2. Potem krótki krok dla każdej encji: nazwa widoczna dla gościa, rodzaj (przełącznik albo przycisk), działanie przycisku, długość impulsu i limit użyć.

Link i PIN pojawią się w powiadomieniach. Każdy panel staje się osobnym urządzeniem w HA.

## Panel w Home Assistancie

Urządzenie panelu ma encje:

| Encja | Zawartość |
| --- | --- |
| Status | Aktywny, Jeszcze nieaktywny, Poza godzinami, Wygasł, Unieważniony albo Zablokowany (zły PIN); w atrybutach liczba błędnych PIN-ów i pozostałe użycia |
| Ważny do | Koniec dostępu |
| Ostatnia akcja gościa | Np. „Gość włączył: Światło garaż”; historia tej encji to dziennik działań gościa |
| Kod QR | Link do panelu jako kod QR, gotowy do pokazania gościowi |
| Link, PIN | Do skopiowania (w sekcji Diagnostyka) |
| Unieważnij | Natychmiast kończy dostęp |

Każde działanie gościa trafia też do dziennika HA i do aktywności urządzenia panelu. **Usunięcie** urządzenia panelu (menu ⋮ → Usuń) unieważnia panel w portalu. Panele, które wygasły ponad 7 dni temu, są usuwane automatycznie.

Jeśli połączenie z portalem nie działa dłużej niż 15 minut, w *Ustawienia → Naprawy* pojawi się zgłoszenie.

## Tworzenie panelu akcją

Przydatne w skryptach i automatyzacjach. *Narzędzia deweloperskie → Akcje*, w trybie YAML:

```yaml
action: temp_access.create_panel
data:
  title: Dostęp dla Marka
  duration:
    hours: 24
  controls:
    - entity_id: light.garaz
      name: Światło garaż
    - entity_id: switch.przekaznik_bramy
      name: Brama wjazdowa
      type: button
      action: pulse
      pulse_seconds: 1
      max_uses: 3
    - entity_id: sensor.temperatura_salon
      name: Temperatura w salonie
```

Link i PIN pojawią się w powiadomieniach Home Assistanta. Wyślij je gościowi **dwiema osobnymi wiadomościami**. Akcja zwraca też `panel_id`, `panel_url` i `pin`, więc można jej używać w skryptach.

### Opcje panelu

| Pole | Znaczenie |
| --- | --- |
| `title` | Tytuł widoczny dla gościa |
| `controls` | Lista kontrolek (patrz niżej), maks. 20 |
| `pin` | 4–8 cyfr; domyślnie losowe 4 cyfry |
| `valid_from` | Początek dostępu; domyślnie teraz |
| `valid_until` albo `duration` | Koniec dostępu albo czas trwania; domyślnie 24 h |
| `days` | Dni tygodnia: `mon` … `sun` |
| `time_from`, `time_to` | Godziny dostępu `GG:MM`; mogą przechodzić przez północ |
| `language` | `pl` (domyślnie) albo `en` |
| `notify` | Czy pokazać powiadomienie z linkiem i PIN-em (domyślnie tak) |

### Kontrolki

| Pole | Znaczenie |
| --- | --- |
| `entity_id` | Encja do sterowania |
| `name` | Nazwa dla gościa; domyślnie nazwa encji |
| `type` | `switch` (przyciski Włącz/Wyłącz), `button` (jeden przycisk, przytrzymanie przez 1 s) albo `sensor` (tylko podgląd wartości) |
| `show_state` | Pokaż gościowi stan przełącznika lub przycisku |
| `action` | Dla przycisku: `press`, `run`, `unlock`, `open`, `toggle`, `pulse` |
| `pulse_seconds` | Długość impulsu dla `pulse`; domyślnie 1 s |
| `max_uses` | Limit użyć |

Obsługiwane domeny i domyślne zachowanie:

| Domena | Domyślny typ | Działanie |
| --- | --- | --- |
| `light`, `switch`, `fan`, `input_boolean`, `siren` | `switch` | włącz / wyłącz; jako przycisk domyślnie `pulse` (`fan`: `toggle`) |
| `cover`, `valve` | `switch` | otwórz / zamknij; jako przycisk domyślnie `toggle` |
| `button`, `input_button` | `button` | `press` |
| `script`, `scene` | `button` | `run` |
| `lock` | `button` | `unlock` (albo `open`) |

Encji z innych domen nie da się udostępnić do sterowania.

### Podgląd stanu

- Rodzaj **`sensor` (Odczyt)** pokazuje gościowi samą wartość, bez sterowania, np. temperaturę, wilgotność, stan drzwi garażowych. Działa dla `sensor`, `binary_sensor`, `input_number`, `input_select`, `input_text`, `counter`, `number`, `select` oraz dla urządzeń sterowalnych (światło, przełącznik, roleta, zamek…).
- Opcja **`show_state: true`** przy przełączniku albo przycisku pokazuje gościowi nad przyciskami np. „Stan: włączone”.

Portal przechowuje tylko ostatnią wartość udostępnionych encji. Home Assistant wysyła odczyty czujników najwyżej co 30 s, a stany sterowanych urządzeń najwyżej co 2 s. Osoby, lokalizacje i kamery są celowo wykluczone.

## Unieważnienie

```yaml
action: temp_access.revoke_panel
data:
  panel_id: P9UFCJSv90vd
```

Prościej: przycisk **Unieważnij** na urządzeniu panelu. Unieważnienie działa w Home Assistancie od razu, nawet gdy portal jest niedostępny.

## Ikona

Ikona integracji (`brand/icon.png`) trafia do Home Assistanta przez oficjalne repozytorium ikon [home-assistant/brands](https://github.com/home-assistant/brands), katalog `custom_integrations/temp_access/`.

## Bezpieczeństwo

- Portal zna tylko nazwy kontrolek (`ctrl_1`, „Światło garaż”), nigdy `entity_id`. Mapowanie na encje istnieje wyłącznie w Home Assistancie.
- Przed każdym wykonaniem Home Assistant sam sprawdza: czy zna panel i kontrolkę, czy panel nie wygasł ani nie został unieważniony, harmonogram, limit użyć oraz to, że polecenie nie jest starsze niż 30 s.
- Polecenia, które przyszły, gdy Home Assistant był offline, nie wykonują się później.
- Każde polecenie wywołuje zdarzenie `temp_access_command` (wynik, panel, kontrolka, encja), na którym można budować własne automatyzacje.

## Testy

Testy działają na prawdziwym Home Assistancie i lokalnie uruchomionym portalu:

```
# w repozytorium portalu
npx wrangler dev --port 8787 --ip 127.0.0.1
# tutaj
pip install pytest-homeassistant-custom-component
pytest
```
