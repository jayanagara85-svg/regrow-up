-- ═══════════════════════════════════════════════════════════════════════════
-- LOOPCHAT MIGRATION — Run AFTER the base Regrow schema is in place.
-- Tables: marketplace_listings, communities, user_communities, channel_posts
-- ═══════════════════════════════════════════════════════════════════════════

-- ─── Marketplace Listings ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS marketplace_listings (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    waste_type      VARCHAR(100) NOT NULL,
    weight          FLOAT,
    price_estimate  FLOAT,
    description     TEXT,
    status          VARCHAR(20) NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open', 'matched', 'completed', 'cancelled')),
    buyer_id        UUID        REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMP   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_listings_user    ON marketplace_listings(user_id);
CREATE INDEX IF NOT EXISTS idx_listings_status  ON marketplace_listings(status);
CREATE INDEX IF NOT EXISTS idx_listings_created ON marketplace_listings(created_at DESC);

-- ─── Communities ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS communities (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(150) NOT NULL,
    area        VARCHAR(150),
    description TEXT,
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP   NOT NULL DEFAULT NOW()
);

-- ─── User ↔ Community memberships ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_communities (
    id           UUID      PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    community_id UUID      NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
    joined_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    is_admin     BOOLEAN   NOT NULL DEFAULT FALSE,
    UNIQUE (user_id, community_id)
);

CREATE INDEX IF NOT EXISTS idx_uc_user      ON user_communities(user_id);
CREATE INDEX IF NOT EXISTS idx_uc_community ON user_communities(community_id);

-- ─── Channel Posts (BBM-style feed) ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS channel_posts (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    title      VARCHAR(200) NOT NULL,
    content    TEXT         NOT NULL,
    category   VARCHAR(50)  NOT NULL DEFAULT 'info',
    author_id  UUID         REFERENCES users(id) ON DELETE SET NULL,
    is_pinned  BOOLEAN      NOT NULL DEFAULT FALSE,
    views      INTEGER      NOT NULL DEFAULT 0,
    created_at TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_posts_pinned  ON channel_posts(is_pinned DESC, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_created ON channel_posts(created_at DESC);

-- ─── Seed: Default community + sample channel post ──────────────────────────
INSERT INTO communities (name, area, description)
VALUES 
    ('Bank Sampah Jakarta Selatan', 'Jakarta Selatan', 'Komunitas bank sampah wilayah Jakarta Selatan'),
    ('Bank Sampah Bandung Tengah', 'Bandung', 'Komunitas bank sampah wilayah Bandung')
ON CONFLICT DO NOTHING;

INSERT INTO channel_posts (title, content, category, is_pinned)
VALUES
    (
        '🎉 Selamat Datang di Regrow LoopChat!',
        'Halo! Regrow LoopChat hadir untuk memudahkan pengelolaan sampah tekstil. '
        'Gunakan WhatsApp untuk booking pickup, jual sampah, dan info terbaru komunitas Anda.',
        'announcement',
        TRUE
    ),
    (
        '♻️ Cara Jual Sampah via WhatsApp',
        'Mudah! Cukup ketik: jual [jenis] [berat]kg\n'
        'Contoh: jual baju bekas 5kg\n'
        'Sistem kami akan langsung membuatkan listing dan mencarikan pembeli.',
        'info',
        FALSE
    )
ON CONFLICT DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════
-- To run this migration:
--   docker exec -i regrow_postgres psql -U regrow -d regrow_db < scripts/migrate_loopchat.sql
-- ═══════════════════════════════════════════════════════════════════════════
