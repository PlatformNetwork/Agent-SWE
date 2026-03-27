package places

import (
    "net/http/httptest"
    "net/url"
    "strings"
    "testing"
    "time"
)

func TestHTTPClientTimeoutExtended(t *testing.T) {
    if httpClient == nil {
        t.Fatal("expected httpClient to be initialized")
    }
    if httpClient.Timeout < 30*time.Second {
        t.Fatalf("expected timeout at least 30s, got %s", httpClient.Timeout)
    }
    if httpClient.Timeout != 35*time.Second {
        t.Fatalf("expected timeout to be 35s, got %s", httpClient.Timeout)
    }
}

func TestRenderPlacesPageIncludesExtendedRadiusAndSortOptions(t *testing.T) {
    req := httptest.NewRequest("GET", "/places", nil)
    html := renderPlacesPage(req)

    if !strings.Contains(html, "value=\"10000\"") || !strings.Contains(html, "10km radius") {
        t.Fatalf("expected 10km radius option to be present")
    }
    if !strings.Contains(html, "value=\"25000\"") || !strings.Contains(html, "25km radius") {
        t.Fatalf("expected 25km radius option to be present")
    }
    if !strings.Contains(html, "value=\"50000\"") || !strings.Contains(html, "50km radius") {
        t.Fatalf("expected 50km radius option to be present")
    }
    if !strings.Contains(html, "name=\"sort\"") {
        t.Fatalf("expected sort selection to be present")
    }
    if !strings.Contains(html, "Sort by distance") || !strings.Contains(html, "Sort by name") {
        t.Fatalf("expected both sort options to be present")
    }
}

func TestRenderPlaceCardMapLinksIncludeNameAndLabel(t *testing.T) {
    place := &Place{
        Name: "Sunrise Bakery",
        Lat:  51.5014,
        Lon:  -0.1419,
    }

    html := renderPlaceCard(place)

    if !strings.Contains(html, "View on Map") {
        t.Fatalf("expected map link label to be 'View on Map'")
    }
    if strings.Contains(html, "View on Google Maps") {
        t.Fatalf("expected old label to be removed")
    }

    escapedQuery := url.QueryEscape(place.Name)
    escapedPath := url.PathEscape(place.Name)
    if !strings.Contains(html, escapedQuery) && !strings.Contains(html, escapedPath) {
        t.Fatalf("expected map link to include encoded place name")
    }
    if !strings.Contains(html, "51.501400") || !strings.Contains(html, "-0.141900") {
        t.Fatalf("expected map link to include coordinates")
    }
}
