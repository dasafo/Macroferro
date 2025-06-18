-- init.sql
-- Script para crear la estructura de la base de datos Macroferro y cargar datos iniciales.

-- Conexión a la base de datos (generalmente no necesario dentro del script si se ejecuta con psql -f o por docker-entrypoint)
-- \c macroferro_db macroferro_user;

BEGIN;

-- Tabla de Categorías
CREATE TABLE IF NOT EXISTS categories (
    category_id INT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    parent_id INT,
    CONSTRAINT fk_parent_category FOREIGN KEY(parent_id) REFERENCES categories(category_id) ON DELETE SET NULL
);
COMMENT ON TABLE categories IS 'Almacena las categorías de los productos, permitiendo jerarquías.';
COMMENT ON COLUMN categories.parent_id IS 'ID de la categoría padre; NULL si es una categoría de nivel superior.';

-- Tabla de Clientes
CREATE TABLE IF NOT EXISTS clients (
    client_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255),
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(50),
    address TEXT
);
COMMENT ON TABLE clients IS 'Información de los clientes de Macroferro.';

-- Tabla de Almacenes
CREATE TABLE IF NOT EXISTS warehouses (
    warehouse_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address TEXT
);
COMMENT ON TABLE warehouses IS 'Almacenes donde se guarda el stock de productos.';

-- Tabla de Imágenes (para URLs únicas)
CREATE TABLE IF NOT EXISTS images (
    image_id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    alt_text VARCHAR(255)
);
COMMENT ON TABLE images IS 'Almacena URLs únicas de imágenes y su texto alternativo.';

-- Tabla de Productos
CREATE TABLE IF NOT EXISTS products (
    sku VARCHAR(50) PRIMARY KEY,
    category_id INT,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    brand VARCHAR(100),
    spec_json JSONB,
    CONSTRAINT fk_category FOREIGN KEY(category_id) REFERENCES categories(category_id) ON DELETE SET NULL
);
COMMENT ON TABLE products IS 'Catálogo de productos ofrecidos por Macroferro.';
COMMENT ON COLUMN products.price IS 'Precio unitario del producto. No puede ser negativo.';
COMMENT ON COLUMN products.spec_json IS 'Especificaciones técnicas del producto en formato JSONB.';

-- Tabla de Unión: Productos <-> Imágenes (Relación muchos-a-muchos)
CREATE TABLE IF NOT EXISTS product_images (
    sku VARCHAR(50) REFERENCES products(sku) ON DELETE CASCADE,
    image_id INT REFERENCES images(image_id) ON DELETE CASCADE,
    PRIMARY KEY (sku, image_id)
);
COMMENT ON TABLE product_images IS 'Tabla de unión para asociar múltiples imágenes a cada producto.';

-- Tabla de Stock
CREATE TABLE IF NOT EXISTS stock (
    stock_id SERIAL PRIMARY KEY,
    sku VARCHAR(50) NOT NULL,
    warehouse_id VARCHAR(50) NOT NULL,
    quantity INT NOT NULL CHECK (quantity >= 0),
    CONSTRAINT fk_product_stock FOREIGN KEY(sku) REFERENCES products(sku) ON DELETE CASCADE,
    CONSTRAINT fk_warehouse_stock FOREIGN KEY(warehouse_id) REFERENCES warehouses(warehouse_id) ON DELETE CASCADE,
    UNIQUE(sku, warehouse_id)
);
COMMENT ON TABLE stock IS 'Cantidad de cada producto en cada almacén.';
COMMENT ON COLUMN stock.quantity IS 'Cantidad disponible del producto en el almacén. No puede ser negativa.';

-- Tabla de Facturas
CREATE TABLE IF NOT EXISTS invoices (
    invoice_id VARCHAR(50) PRIMARY KEY,
    client_id VARCHAR(50),
    total NUMERIC(10, 2) NOT NULL CHECK (total >= 0),
    pdf_url TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_client_invoice FOREIGN KEY(client_id) REFERENCES clients(client_id) ON DELETE SET NULL
);
COMMENT ON TABLE invoices IS 'Facturas generadas para los pedidos de los clientes.';
COMMENT ON COLUMN invoices.total IS 'Monto total de la factura. No puede ser negativo.';

-- Tabla de Items de Factura
CREATE TABLE IF NOT EXISTS invoice_items (
    item_id SERIAL PRIMARY KEY,
    invoice_id VARCHAR(50) NOT NULL,
    sku VARCHAR(50) NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    price_at_purchase NUMERIC(10, 2) NOT NULL CHECK (price_at_purchase >= 0),
    CONSTRAINT fk_invoice_item FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id) ON DELETE CASCADE,
    CONSTRAINT fk_product_item FOREIGN KEY(sku) REFERENCES products(sku) ON DELETE RESTRICT
);
COMMENT ON TABLE invoice_items IS 'Detalle de los productos incluidos en cada factura.';
COMMENT ON COLUMN invoice_items.quantity IS 'Cantidad del producto vendido. Debe ser mayor que cero.';
COMMENT ON COLUMN invoice_items.price_at_purchase IS 'Precio unitario del producto al momento de la compra.';
COMMENT ON CONSTRAINT fk_product_item ON invoice_items IS 'Restringe el borrado de un producto si está referenciado en alguna factura.';

--------------------------------------------------------------------------------
-- CARGA DE DATOS DESDE ARCHIVOS CSV                                          --
-- Asegúrate de que los archivos CSV estén en /docker-entrypoint-initdb.d/csv_data/ --
-- Y que los encabezados de los CSV coincidan con las columnas de las tablas. --
--------------------------------------------------------------------------------

-- El orden de carga es importante debido a las Foreign Keys.

COPY categories(category_id, name, parent_id) FROM '/docker-entrypoint-initdb.d/csv_data/categories.csv' WITH CSV HEADER DELIMITER ',';
COPY clients(client_id, name, email, phone, address) FROM '/docker-entrypoint-initdb.d/csv_data/clients.csv' WITH CSV HEADER DELIMITER ',';
COPY warehouses(warehouse_id, name, address) FROM '/docker-entrypoint-initdb.d/csv_data/warehouses.csv' WITH CSV HEADER DELIMITER ',';

-- Productos depende de categories
COPY products(sku, category_id, name, description, price, brand, spec_json) FROM '/docker-entrypoint-initdb.d/csv_data/products.csv' WITH CSV HEADER DELIMITER ',';

-- Carga de imágenes
-- Paso 1: Cargar el CSV de imágenes en una tabla temporal
CREATE TEMP TABLE temp_images_load (
    sku VARCHAR(50),
    url TEXT,
    alt_text VARCHAR(255)
);
COPY temp_images_load FROM '/docker-entrypoint-initdb.d/csv_data/images.csv' WITH CSV HEADER DELIMITER ',';

-- Paso 2: Insertar URLs únicas en la tabla 'images'
INSERT INTO images (url, alt_text)
SELECT DISTINCT url, alt_text
FROM temp_images_load
ON CONFLICT (url) DO NOTHING; -- Evita duplicados si varias SKUs usan la misma URL de imagen

-- Paso 3: Poblar la tabla de unión 'product_images'
INSERT INTO product_images (sku, image_id)
SELECT til.sku, i.image_id
FROM temp_images_load til
JOIN images i ON til.url = i.url
JOIN products p ON til.sku = p.sku -- Asegurar que el SKU exista en products
ON CONFLICT (sku, image_id) DO NOTHING; -- Evitar duplicados en la tabla de unión

DROP TABLE temp_images_load; -- Limpiar tabla temporal

-- Stock depende de products y warehouses
COPY stock(sku, warehouse_id, quantity) FROM '/docker-entrypoint-initdb.d/csv_data/stock.csv' WITH CSV HEADER DELIMITER ',';

-- Invoices depende de clients
COPY invoices(invoice_id, client_id, total, pdf_url, created_at) FROM '/docker-entrypoint-initdb.d/csv_data/invoices.csv' WITH CSV HEADER DELIMITER ',';

-- Invoice_items depende de invoices y products
COPY invoice_items(invoice_id, sku, quantity, price_at_purchase) FROM '/docker-entrypoint-initdb.d/csv_data/invoice_items.csv' WITH CSV HEADER DELIMITER ',';

-- Finalizar la transacción
COMMIT;

\echo 'Macroferro database initialized successfully.'
