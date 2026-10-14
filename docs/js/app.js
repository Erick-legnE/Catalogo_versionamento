/**
 * Unified Catalog Application
 * Shared engine for Clientes and Representantes
 */

const CatalogApp = {
    products: [],
    filteredProducts: [],

    init: async function() {
        this.bindEvents();
        await this.loadData();
        this.renderSafeGrid();
    },

    bindEvents: function() {
        const searchInput = document.getElementById('search-input');
        const categoryFilter = document.getElementById('category-filter');

        if (searchInput) {
            searchInput.addEventListener('input', (e) => this.handleSearch(e.target.value));
        }

        if (categoryFilter) {
            categoryFilter.addEventListener('change', (e) => this.handleFilter(e.target.value));
        }
    },

    loadData: async function() {
        try {
            const response = await fetch('./produtos.json');
            if (!response.ok) {
                throw new Error(`Failed to load data (HTTP ${response.status})`);
            }
            this.products = await response.json();
            this.filteredProducts = [...this.products];
            this.populateCategories();
        } catch (error) {
            console.error('Error loading product catalog:', error);
            const grid = document.getElementById('product-grid');
            if (grid) {
                grid.innerHTML = `
                    <div class="empty-state error-state">
                        <p>Não foi possível carregar os produtos deste catálogo.</p>
                    </div>`;
            }
        }
    },

    populateCategories: function() {
        const categoryFilter = document.getElementById('category-filter');
        if (!categoryFilter) return;

        const categories = [...new Set(this.products.map(p => p.categoria).filter(Boolean))].sort();
        
        let options = '<option value="">Todas as Categorias</option>';
        categories.forEach(cat => {
            options += `<option value="${cat}">${cat}</option>`;
        });
        
        categoryFilter.innerHTML = options;
    },

    extractColorCode: function(colorText) {
        if (!colorText) return null;
        const match = colorText.match(/C\s*[-_]?\s*(\d{3,4})/i);
        return match ? 'C' + match[1] : null;
    },

    handleImageError: function(imgElement, colorName) {
        if (imgElement.dataset.fallbackAttempted) {
            imgElement.src = '../../imagens/placeholder.png';
            return;
        }

        imgElement.dataset.fallbackAttempted = 'true';
        const colorCode = this.extractColorCode(colorName);

        if (colorCode) {
            imgElement.src = `../../imagens/pastilhas/pastilha_${colorCode}.png`;
        } else {
            imgElement.src = '../../imagens/placeholder.png';
        }
    },

    handleSearch: function(query) {
        const category = document.getElementById('category-filter')?.value || '';
        this.applyFilters(query, category);
    },

    handleFilter: function(category) {
        const query = document.getElementById('search-input')?.value || '';
        this.applyFilters(query, category);
    },

    applyFilters: function(query, category) {
        const q = query.toLowerCase().trim();

        this.filteredProducts = this.products.filter(item => {
            const matchesQuery = !q || 
                (item.nome && item.nome.toLowerCase().includes(q)) ||
                (item.codigo && item.codigo.toLowerCase().includes(q)) ||
                (item.cor_nome && item.cor_nome.toLowerCase().includes(q)) ||
                (item.cor_codigo && item.cor_codigo.toLowerCase().includes(q));

            const matchesCategory = !category || item.categoria === category;

            return matchesQuery && matchesCategory;
        });

        this.renderSafeGrid();
    },

    renderSafeGrid: function() {
        const grid = document.getElementById('product-grid');
        const countEl = document.getElementById('product-count');
        if (countEl) countEl.textContent = `${this.filteredProducts.length} produto(s) encontrado(s)`;
        if (!grid) return;
        if (!this.filteredProducts.length) {
            grid.replaceChildren();
            const empty = document.createElement('div');
            empty.className = 'empty-state';
            const message = document.createElement('p');
            message.textContent = 'Nenhum produto encontrado com os filtros selecionados.';
            empty.append(message);
            grid.append(empty);
            return;
        }

        const fragment = document.createDocumentFragment();
        this.filteredProducts.forEach(item => {
            const rawColor = item.cor_nome || item.cor_codigo || '';
            const article = document.createElement('article');
            article.className = 'product-card';
            const imageContainer = document.createElement('div');
            imageContainer.className = 'product-image-container';
            const image = document.createElement('img');
            image.className = 'product-image';
            image.loading = 'lazy';
            image.alt = String(item.nome || 'Produto');
            image.src = String(item.imagem_url || '../../imagens/placeholder.png');
            image.addEventListener('error', () => this.handleImageError(image, rawColor));
            imageContainer.append(image);
            if (item.cor_codigo) {
                const badge = document.createElement('span');
                badge.className = 'color-badge';
                badge.textContent = String(item.cor_codigo);
                imageContainer.append(badge);
            }
            const info = document.createElement('div');
            info.className = 'product-info';
            const code = document.createElement('span');
            code.className = 'product-code';
            code.textContent = String(item.codigo || 'S/C');
            const title = document.createElement('h3');
            title.className = 'product-title';
            title.textContent = String(item.nome || 'Produto sem nome');
            const details = document.createElement('div');
            details.className = 'product-details';
            const color = document.createElement('p');
            color.className = 'product-color';
            color.textContent = `Cor: ${String(item.cor_nome || 'N/A')}`;
            details.append(color);
            if (item.categoria) {
                const category = document.createElement('p');
                category.className = 'product-category';
                category.textContent = `Categoria: ${String(item.categoria)}`;
                details.append(category);
            }
            info.append(code, title, details);
            article.append(imageContainer, info);
            fragment.append(article);
        });
        grid.replaceChildren(fragment);
    },

    renderGrid: function() {
        const grid = document.getElementById('product-grid');
        const countEl = document.getElementById('product-count');

        if (countEl) {
            countEl.textContent = `${this.filteredProducts.length} produto(s) encontrado(s)`;
        }

        if (!grid) return;

        if (this.filteredProducts.length === 0) {
            grid.innerHTML = `
                <div class="empty-state">
                    <p>Nenhum produto encontrado com os filtros selecionados.</p>
                </div>`;
            return;
        }

        grid.innerHTML = this.filteredProducts.map(item => {
            const rawColor = item.cor_nome || item.cor_codigo || '';
            const colorBadgeHtml = item.cor_codigo 
                ? `<span class="color-badge">${item.cor_codigo}</span>` 
                : '';

            return `
                <article class="product-card">
                    <div class="product-image-container">
                        <img 
                            src="${item.imagem_url}" 
                            alt="${item.nome}" 
                            class="product-image"
                            loading="lazy"
                            onerror="CatalogApp.handleImageError(this, '${rawColor}')"
                        >
                        ${colorBadgeHtml}
                    </div>
                    <div class="product-info">
                        <span class="product-code">${item.codigo || 'S/C'}</span>
                        <h3 class="product-title">${item.nome}</h3>
                        <div class="product-details">
                            <p class="product-color"><strong>Cor:</strong> ${item.cor_nome || 'N/A'}</p>
                            ${item.categoria ? `<p class="product-category"><strong>Categoria:</strong> ${item.categoria}</p>` : ''}
                        </div>
                    </div>
                </article>
            `;
        }).join('');
    }
};

document.addEventListener('DOMContentLoaded', () => CatalogApp.init());
