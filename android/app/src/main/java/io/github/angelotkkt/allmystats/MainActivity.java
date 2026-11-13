package io.github.angelotkkt.allmystats;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.res.AssetManager;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import com.google.mlkit.vision.barcode.common.Barcode;
import com.google.mlkit.vision.codescanner.GmsBarcodeScanner;
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions;
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * AllMyStats sur Android, AUTONOME : le moteur d'AllMyStats (le même que sur le PC) tourne dans le téléphone.
 * Une seule fois, on scanne le QR code du PC : le téléphone copie tes réglages, tes clés et tes stats.
 * Ensuite il récupère ses stats tout seul sur Internet, sans le PC.
 */
public class MainActivity extends Activity {

    private static final String ACCUEIL = "file:///android_asset/accueil.html";
    private static final String CHARGEMENT = "file:///android_asset/chargement.html";
    private static final int CHOIX_FICHIER = 42;
    private static final int PORT_VOULU = 8765;

    private static boolean moteurLance = false;
    private static int port = 0;

    private WebView vue;
    private SharedPreferences prefs;
    private File donnees, web;
    private ValueCallback<Uri[]> rappelFichier;
    private final Handler principal = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle etat) {
        super.onCreate(etat);
        prefs = getSharedPreferences("allmystats", MODE_PRIVATE);
        donnees = new File(getFilesDir(), "donnees");
        web = new File(getFilesDir(), "web");
        donnees.mkdirs();

        vue = new WebView(this);
        vue.setBackgroundColor(0xFF141832);
        setContentView(vue);
        WebSettings r = vue.getSettings();
        r.setJavaScriptEnabled(true);
        r.setDomStorageEnabled(true);
        r.setMediaPlaybackRequiresUserGesture(true);
        r.setSupportMultipleWindows(false);
        r.setAllowFileAccess(false);
        r.setUserAgentString(r.getUserAgentString() + " AllMyStatsAndroid/2");
        CookieManager.getInstance().setAcceptCookie(true);
        vue.addJavascriptInterface(new Pont(), "Android");
        vue.setWebViewClient(new Client());
        vue.setWebChromeClient(new Chrome());

        copierInterface();
        if (traiterLien(getIntent())) return;
        if (estLie()) lancerMoteur();
        else vue.loadUrl(ACCUEIL);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        traiterLien(intent);
    }

    @Override
    public void onBackPressed() {
        String url = vue.getUrl();
        if (url != null && url.startsWith(ACCUEIL) && estLie()) {
            ouvrirStats();
        } else if (vue.canGoBack()) {
            vue.goBack();
        } else {
            super.onBackPressed();
        }
    }

    private boolean estLie() {
        return new File(donnees, "config.json").exists();
    }

    // ------------------------------------------------------------------ le moteur (Python) dans le téléphone

    /** L'interface (dossier web) est copiée hors de l'APK pour que le moteur puisse la servir. */
    private void copierInterface() {
        int version = 0;
        try {
            version = getPackageManager().getPackageInfo(getPackageName(), 0).versionCode;
        } catch (Exception ignore) {
        }
        if (prefs.getInt("web_version", -1) == version && new File(web, "index.html").exists()) return;
        try {
            copierDossier(getAssets(), "web", web);
            prefs.edit().putInt("web_version", version).apply();
        } catch (Exception e) {
            // l'erreur s'affichera au démarrage du moteur
        }
    }

    private static void copierDossier(AssetManager assets, String chemin, File cible) throws Exception {
        String[] liste = assets.list(chemin);
        if (liste == null || liste.length == 0) {
            try (InputStream in = assets.open(chemin); OutputStream out = new FileOutputStream(cible)) {
                copier(in, out);
            }
            return;
        }
        cible.mkdirs();
        for (String nom : liste) copierDossier(assets, chemin + "/" + nom, new File(cible, nom));
    }

    private static void copier(InputStream in, OutputStream out) throws Exception {
        byte[] tampon = new byte[16384];
        int n;
        while ((n = in.read(tampon)) > 0) out.write(tampon, 0, n);
    }

    private void lancerMoteur() {
        vue.loadUrl(CHARGEMENT);
        if (moteurLance && port > 0) {
            ouvrirStats();
            return;
        }
        if (!moteurLance) {
            moteurLance = true;
            new File(donnees, "port.txt").delete();
            new File(donnees, "erreur_demarrage.txt").delete();
            final String d = donnees.getAbsolutePath(), w = web.getAbsolutePath();
            new Thread(() -> {
                try {
                    if (!Python.isStarted()) Python.start(new AndroidPlatform(getApplicationContext()));
                    Python.getInstance().getModule("ams_android").callAttr("demarrer", d, w, PORT_VOULU);
                } catch (Throwable t) {
                    moteurLance = false;
                    montrerMessage("AllMyStats n'a pas pu démarrer : " + t.getMessage());
                }
            }, "moteur").start();
        }
        new Thread(this::attendreMoteur, "attente").start();
    }

    private void attendreMoteur() {
        long fin = System.currentTimeMillis() + 90000;
        while (System.currentTimeMillis() < fin) {
            File erreur = new File(donnees, "erreur_demarrage.txt");
            if (erreur.exists()) {
                String[] lignes = lireFichier(erreur).trim().split("\n");
                montrerMessage("AllMyStats n'a pas pu démarrer : " + lignes[lignes.length - 1]);
                return;
            }
            File fichierPort = new File(donnees, "port.txt");
            if (fichierPort.exists()) {
                try {
                    int p = Integer.parseInt(lireFichier(fichierPort).trim());
                    HttpURLConnection c = (HttpURLConnection) new URL("http://127.0.0.1:" + p + "/api/ping").openConnection();
                    c.setConnectTimeout(1000);
                    c.setReadTimeout(2000);
                    if (c.getResponseCode() == 200) {
                        port = p;
                        principal.post(this::ouvrirStats);
                        return;
                    }
                } catch (Exception ignore) {
                }
            }
            try {
                Thread.sleep(300);
            } catch (InterruptedException e) {
                return;
            }
        }
        montrerMessage("AllMyStats met trop de temps à démarrer. Ferme l'appli et rouvre-la.");
    }

    private void ouvrirStats() {
        if (port <= 0) {
            lancerMoteur();
            return;
        }
        vue.clearHistory();
        vue.loadUrl("http://127.0.0.1:" + port + "/");
    }

    private static String lireFichier(File f) {
        try (InputStream in = new FileInputStream(f)) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            copier(in, out);
            return out.toString("UTF-8");
        } catch (Exception e) {
            return "";
        }
    }

    // ------------------------------------------------------------------ liaison avec le PC (une fois)

    /** Lien allmystats://relier?h=IP:PORT&c=CODE (QR code du PC). */
    private boolean traiterLien(Intent intent) {
        if (intent == null || intent.getData() == null) return false;
        Uri u = intent.getData();
        if (!"allmystats".equals(u.getScheme())) return false;
        String h = u.getQueryParameter("h"), c = u.getQueryParameter("c");
        if (h == null || c == null) return false;
        vue.loadUrl(ACCUEIL);
        relier(h, c);
        return true;
    }

    private void montrerMessage(final String texte) {
        principal.post(() -> {
            if (vue.getUrl() == null || !vue.getUrl().startsWith(ACCUEIL)) vue.loadUrl(ACCUEIL);
            principal.postDelayed(() -> vue.evaluateJavascript(
                    "window.afficherMessage && afficherMessage(" + JSONObject.quote(texte) + ")", null), 500);
        });
    }

    private void montrerAvancement(final String texte) {
        principal.post(() -> vue.evaluateJavascript(
                "window.afficherAvancement && afficherAvancement(" + JSONObject.quote(texte) + ")", null));
    }

    /** Télécharge une fois depuis le PC : réglages, clés, stats et fichiers des jeux. Puis le téléphone est autonome. */
    private void relier(String hoteBrut, String codeBrut) {
        final String h = hoteBrut.trim().replaceFirst("^https?://", "").replaceAll("/.*$", "");
        final String hote = h.contains(":") ? h : h + ":8790";
        final String code = codeBrut.trim().toUpperCase().replace("-", "").replace(" ", "");
        montrerAvancement("Connexion à ton PC…");
        new Thread(() -> {
            HttpURLConnection cnx = null;
            try {
                cnx = (HttpURLConnection) new URL("http://" + hote + "/api/telephone/export").openConnection();
                cnx.setRequestProperty("X-AMS-Code", code);
                cnx.setConnectTimeout(6000);
                cnx.setReadTimeout(60000);
                int statut = cnx.getResponseCode();
                if (statut == 401 || statut == 403) {
                    montrerMessage("Code incorrect. Regarde le code dans AllMyStats sur ton PC : Paramètres > Téléphone.");
                    return;
                }
                if (statut == 429) {
                    montrerMessage("Trop d'essais : attends 10 minutes puis réessaie.");
                    return;
                }
                if (statut != 200) {
                    montrerMessage("Ton PC a répondu une erreur (" + statut + "). Mets AllMyStats à jour sur le PC puis réessaie.");
                    return;
                }
                montrerAvancement("Copie de tes comptes et de tes stats…");
                int fichiers = extraire(cnx.getInputStream());
                if (fichiers == 0 || !estLie()) {
                    montrerMessage("Rien reçu du PC. Mets AllMyStats à jour sur le PC puis réessaie.");
                    return;
                }
                prefs.edit().putString("pc", hote).putLong("synchro", System.currentTimeMillis()).apply();
                principal.post(() -> {
                    if (moteurLance && port > 0) ouvrirStats();
                    else lancerMoteur();
                });
            } catch (Exception e) {
                montrerMessage("Ton PC ne répond pas à l'adresse " + hote + ". Vérifie qu'il est allumé, qu'AllMyStats "
                        + "est lancé avec « Relier mon téléphone » coché, et que le téléphone est sur le même Wi-Fi.");
            } finally {
                if (cnx != null) cnx.disconnect();
            }
        }).start();
    }

    /** Range le paquet du PC dans le dossier de données (chaque fichier remplacé d'un coup). */
    private int extraire(InputStream flux) throws Exception {
        int n = 0;
        String racine = donnees.getCanonicalPath() + File.separator;
        try (ZipInputStream zip = new ZipInputStream(flux)) {
            ZipEntry e;
            while ((e = zip.getNextEntry()) != null) {
                if (e.isDirectory()) continue;
                File cible = new File(donnees, e.getName());
                if (!cible.getCanonicalPath().startsWith(racine)) continue;   // sécurité : rien hors du dossier
                File tmp = new File(cible.getPath() + ".nouveau");
                try (OutputStream out = new FileOutputStream(tmp)) {
                    copier(zip, out);
                }
                if (!tmp.renameTo(cible)) {
                    cible.delete();
                    tmp.renameTo(cible);
                }
                n++;
            }
        }
        return n;
    }

    private void scanner() {
        GmsBarcodeScannerOptions options = new GmsBarcodeScannerOptions.Builder()
                .setBarcodeFormats(Barcode.FORMAT_QR_CODE)
                .build();
        GmsBarcodeScanner lecteur = GmsBarcodeScanning.getClient(this, options);
        lecteur.startScan()
                .addOnSuccessListener(code -> {
                    String texte = code.getRawValue();
                    if (texte != null && texte.startsWith("allmystats://")) {
                        Uri u = Uri.parse(texte);
                        String h = u.getQueryParameter("h"), c = u.getQueryParameter("c");
                        if (h != null && c != null) {
                            relier(h, c);
                            return;
                        }
                    }
                    montrerMessage("Ce QR code n'est pas celui d'AllMyStats. Sur ton PC : Paramètres > Téléphone.");
                })
                .addOnFailureListener(e -> montrerMessage(
                        "Le lecteur de QR code n'a pas pu s'ouvrir. Tape l'adresse et le code à la place."));
    }

    // ------------------------------------------------------------------ pont avec les pages

    private class Pont {
        @JavascriptInterface
        public void scannerQr() {
            principal.post(MainActivity.this::scanner);
        }

        @JavascriptInterface
        public void relierPc(String h, String c) {
            relier(h, c);
        }

        @JavascriptInterface
        public String dernierPc() {
            return prefs.getString("pc", "");
        }

        @JavascriptInterface
        public boolean dejaLie() {
            return estLie();
        }

        @JavascriptInterface
        public void synchroniser() {
            principal.post(() -> vue.loadUrl(ACCUEIL));
        }

        @JavascriptInterface
        public void retour() {
            principal.post(MainActivity.this::ouvrirStats);
        }

        @JavascriptInterface
        public String version() {
            try {
                return getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
            } catch (Exception e) {
                return "";
            }
        }
    }

    // ------------------------------------------------------------------ navigation

    private class Client extends WebViewClient {
        @Override
        public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest req) {
            Uri u = req.getUrl();
            String s = u.toString();
            if (s.startsWith("file:///android_asset/")) return false;
            if ("allmystats".equals(u.getScheme())) {
                traiterLien(new Intent(Intent.ACTION_VIEW, u));
                return true;
            }
            if ("127.0.0.1".equals(u.getHost()) && u.getPort() == port) return false;   // AllMyStats dans le téléphone
            // Tout le reste (sites des jeux, Genshin-Builds, cartes, pages des clés…) : dans le navigateur
            try {
                startActivity(new Intent(Intent.ACTION_VIEW, u));
            } catch (ActivityNotFoundException e) {
                // pas de navigateur
            }
            return true;
        }
    }

    private class Chrome extends WebChromeClient {
        @Override
        public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> rappel, FileChooserParams params) {
            if (rappelFichier != null) rappelFichier.onReceiveValue(null);
            rappelFichier = rappel;
            try {
                startActivityForResult(params.createIntent(), CHOIX_FICHIER);
            } catch (ActivityNotFoundException e) {
                rappelFichier = null;
                return false;
            }
            return true;
        }
    }

    @Override
    protected void onActivityResult(int demande, int resultat, Intent donneesIntent) {
        if (demande == CHOIX_FICHIER && rappelFichier != null) {
            rappelFichier.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultat, donneesIntent));
            rappelFichier = null;
            return;
        }
        super.onActivityResult(demande, resultat, donneesIntent);
    }
}
