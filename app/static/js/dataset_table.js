/**
 * Alpine.js `datasetTable` component.
 *
 * Drives the interactive dataset table on `datasets/show.html`: a debounced
 * global search, per-column filters, click-to-sort headers, a page-size
 * selector and pagination controls. Every change re-fetches rows from the
 * server-side rows JSON API, so all filtering/sorting/paging happens on the
 * server.
 *
 * Takes no arguments: `x-data="datasetTable"`. Configuration comes from
 * `data-rows-url` / `data-max-page-size` on the mounted element, and the
 * initial page of rows comes from the `#initial-page` JSON script tag. See
 * `app/templates/datasets/show.html`.
 */
document.addEventListener("alpine:init", () => {
  const DEBOUNCE_MS = 300;

  Alpine.data("datasetTable", () => ({
    rowsUrl: "",
    maxPageSize: 0,
    columns: [],
    rows: [],
    page: 1,
    perPage: 25,
    total: 0,
    totalPages: 1,
    search: "",
    filters: Object.create(null),
    sortBy: null,
    sortDir: null,
    loading: false,
    error: null,

    _requestId: 0,
    _debounceTimer: null,

    init() {
      this.rowsUrl = this.$el.dataset.rowsUrl;
      this.maxPageSize = Number(this.$el.dataset.maxPageSize);

      const initial = JSON.parse(document.getElementById("initial-page").textContent);
      this.columns = initial.columns;
      this.rows = initial.rows;
      this.page = initial.page;
      this.perPage = initial.per_page;
      this.total = initial.total;
      this.totalPages = initial.total_pages;

      this.filters = Object.create(null);
      for (const column of this.columns) {
        this.filters[column.name] = "";
      }

      this.$watch("search", () => this._debouncedRefetch());
      this.$watch("filters", () => this._debouncedRefetch());
      this.$watch("perPage", () => {
        this.page = 1;
        this.fetchRows();
      });
    },

    _debouncedRefetch() {
      if (this._debounceTimer) {
        clearTimeout(this._debounceTimer);
      }
      this._debounceTimer = setTimeout(() => {
        this.page = 1;
        this.fetchRows();
      }, DEBOUNCE_MS);
    },

    _buildParams() {
      const params = new URLSearchParams();
      params.set("page", String(this.page));
      params.set("per_page", String(this.perPage));
      if (this.search) {
        params.set("q", this.search);
      }
      if (this.sortBy) {
        params.set("sort", this.sortBy);
        params.set("dir", this.sortDir);
      }
      for (const [column, value] of Object.entries(this.filters)) {
        if (value) {
          params.set(`filter[${column}]`, value);
        }
      }
      return params;
    },

    async fetchRows() {
      const requestId = ++this._requestId;
      const params = this._buildParams();
      this.loading = true;

      let response;
      try {
        response = await fetch(`${this.rowsUrl}?${params}`);
      } catch {
        if (requestId !== this._requestId) return;
        this.loading = false;
        this.error = "Unable to reach the server. Please try again.";
        return;
      }

      let payload = null;
      try {
        payload = await response.json();
      } catch {
        payload = null;
      }

      if (requestId !== this._requestId) return;

      this.loading = false;

      if (!response.ok) {
        this.error = payload && payload.error ? payload.error : "Something went wrong.";
        return;
      }

      this.error = null;
      this.columns = payload.columns;
      this.rows = payload.rows;
      this.page = payload.page;
      this.perPage = payload.per_page;
      this.total = payload.total;
      this.totalPages = payload.total_pages;
    },

    toggleSort(col) {
      if (this.sortBy !== col) {
        this.sortBy = col;
        this.sortDir = "asc";
      } else if (this.sortDir === "asc") {
        this.sortDir = "desc";
      } else {
        this.sortBy = null;
        this.sortDir = null;
      }
      this.page = 1;
      this.fetchRows();
    },

    goTo(page) {
      const target = Math.min(Math.max(page, 1), this.totalPages);
      if (target === this.page) return;
      this.page = target;
      this.fetchRows();
    },

    clearFilters() {
      this.search = "";
      for (const column of this.columns) {
        this.filters[column.name] = "";
      }
    },

    get rangeStart() {
      const start = this.total === 0 ? 0 : (this.page - 1) * this.perPage + 1;
      return start.toLocaleString();
    },

    get rangeEnd() {
      return Math.min(this.page * this.perPage, this.total).toLocaleString();
    },
  }));
});
