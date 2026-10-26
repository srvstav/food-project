package com.muj.mess.db;

import com.muj.mess.config.AppConfig;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.GeneralSecurityException;
import java.security.KeyStore;
import java.security.cert.CertificateFactory;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.Properties;

/**
 * Opens MySQL connections and runs work inside a transaction.
 *
 * OOP: Encapsulation — the URL, user and password are private. The rest of the app never sees them;
 * it only asks "run this work for me" through inTransaction().
 */
public class Database {

    private final String url;
    private final Properties props;

    // OOP: Constructor — builds a ready-to-use Database object from the settings.
    public Database(AppConfig config) {
        this.url = "jdbc:mysql://" + config.dbHost() + ":" + config.dbPort() + "/" + config.dbName();
        this.props = new Properties();
        props.setProperty("user", config.dbUser());
        props.setProperty("password", config.dbPassword());
        props.setProperty("characterEncoding", "UTF-8");
        props.setProperty("connectTimeout", "10000");
        if (config.dbSslCa() != null) {
            props.setProperty("sslMode", "VERIFY_CA");
            props.setProperty("trustCertificateKeyStoreUrl", "file:" + trustStoreFrom(config.dbSslCa()));
            props.setProperty("trustCertificateKeyStoreType", "PKCS12");
            props.setProperty("trustCertificateKeyStorePassword", TRUST_PASSWORD);
        }
    }

    private static final String TRUST_PASSWORD = "mess-ca";

    /** Java can't read a .pem file as a trust store, so copy the cloud's CA certificate into a PKCS12 file. */
    private static String trustStoreFrom(String pemPath) {
        try (InputStream in = Files.newInputStream(Path.of(pemPath))) {
            KeyStore store = KeyStore.getInstance("PKCS12");
            store.load(null, null);
            store.setCertificateEntry("ca", CertificateFactory.getInstance("X.509").generateCertificate(in));
            Path out = Files.createTempFile("mess-ca", ".p12");
            try (OutputStream os = Files.newOutputStream(out)) {
                store.store(os, TRUST_PASSWORD.toCharArray());
            }
            return out.toUri().getPath();
        } catch (IOException | GeneralSecurityException e) {
            throw new IllegalStateException("Could not read the CA certificate " + pemPath, e);
        }
    }

    /**
     * One connection per request: commit if the work succeeds, roll back if anything throws.
     * OOP: Generic method — <T> lets the caller get back exactly the type its work returns.
     */
    public <T> T inTransaction(SqlWork<T> work) throws SQLException {
        // try-with-resources: the connection is closed automatically, even after an error.
        try (Connection conn = DriverManager.getConnection(url, props)) {
            conn.setAutoCommit(false);
            try (Statement st = conn.createStatement()) {
                st.execute("SET time_zone = '+05:30'"); // CURRENT_TIMESTAMP in MySQL = India time, like the app
            }
            try {
                T result = work.run(conn); // OOP: Polymorphism — whatever lambda was passed in runs here
                conn.commit();
                return result;
            } catch (SQLException | RuntimeException e) {
                conn.rollback();
                throw e;
            }
        }
    }
}
