// Copyright 2026 Blink Labs Software
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
// implied. See the License for the specific language governing
// permissions and limitations under the License.

package blockfrost

import (
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/require"
)

func TestParsePaginationDefaultsAndClamping(t *testing.T) {
	req := httptest.NewRequest(
		http.MethodGet,
		"/endpoint?count=250&page=0&order=DESC",
		nil,
	)

	params, err := ParsePagination(req)
	require.NoError(t, err)
	require.Equal(t, MaxPaginationCount, params.Count)
	require.Equal(t, 1, params.Page)
	require.Equal(t, PaginationOrderDesc, params.Order)
}

func TestParsePaginationInvalidValues(t *testing.T) {
	badCount := httptest.NewRequest(
		http.MethodGet,
		"/endpoint?count=not-a-number",
		nil,
	)
	_, err := ParsePagination(badCount)
	require.Error(t, err)
	require.True(
		t,
		errors.Is(err, ErrInvalidPaginationParameters),
	)

	badOrder := httptest.NewRequest(
		http.MethodGet,
		"/endpoint?order=sideways",
		nil,
	)
	_, err = ParsePagination(badOrder)
	require.Error(t, err)
	require.True(
		t,
		errors.Is(err, ErrInvalidPaginationParameters),
	)
}

func TestSetPaginationHeadersTotals(t *testing.T) {
	recorder := httptest.NewRecorder()
	params := PaginationParams{
		Count: 50,
		Page:  3,
		Order: PaginationOrderAsc,
	}

	SetPaginationHeaders(recorder, 205, params)
	require.Equal(
		t,
		"205",
		recorder.Header().Get("X-Pagination-Count-Total"),
	)
	require.Equal(
		t,
		"5",
		recorder.Header().Get("X-Pagination-Page-Total"),
	)
}

func TestSetPaginationHeadersDefaultsOnInvalidCount(t *testing.T) {
	recorder := httptest.NewRecorder()
	params := PaginationParams{
		Count: 0,
		Page:  1,
		Order: PaginationOrderAsc,
	}

	SetPaginationHeaders(recorder, -10, params)
	require.Equal(
		t,
		"0",
		recorder.Header().Get("X-Pagination-Count-Total"),
	)
	require.Equal(
		t,
		"0",
		recorder.Header().Get("X-Pagination-Page-Total"),
	)
}
