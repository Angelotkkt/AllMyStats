package io.github.angelotkkt.allmystats;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import com.google.mlkit.vision.barcode.common.Barcode;
import com.google.mlkit.vision.codescanner.GmsBarcodeScanner;
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions;
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning;

import org.json.JSONObject;

import java.net.HttpURLConnection;
import java.net.URL;
import java.util.List;
import java.util.Map;

/**
 * AllMyStats sur Android : affiche AllMyStats de ton PC, par ton Wi-Fi.
 * La première fois, on relie le téléphone au PC (QR code ou adresse + code affichés sur le PC,
 * dans Paramètres > Téléphone). Ensuite l'appli s'ouvre directement sur tes stats.
 */
public class MainActivity extends Activity {

    private static final String ACCUEIL = "file:///android_asset/accueil.html";
    private static final String HORS_LIGNE = "file:///android_asset/hors_ligne.html";
    private static final int CHOIX_FICHIER = 42;

    private WebView vue;
    private SharedPreferences prefs;
    private ValueCallback<Uri[]> rappelFichier;
    private final Handler principal = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle etat) {
        super.onCreate(etat);
        prefs = getSharedPreferences("allmystats", MODE_PRIVATE);
        vue = new WebView(this);
        vue.setBackgroundColor(0xFF141832);
        setContentView(vue);

        WebSettings r = vue.getSettings();
        r.setJavaScriptEnabled(true);
        r.setDomStorageEnabled(true);
        r.setMediaPlaybackRequiresUserGesture(true);
        r.setSupportMultipleWindows(false);
        r.setAllowFileAccess(false);
        r.setUserAgentString(r.getUserAgentString() + " AllMyStatsAndroid/1");
        CookieManager.getInstance().setAcceptCookie(true);

        vue.addJavascriptInterface(new Pont(), "Android");
        vue.setWebViewClient(new Client());
        vue.setWebChromeClient(new Chrome());

        if (!traiterLien(getIntent())) ouvrirDepart();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        traiterLien(intent);
    }

    @Override
    protected void onPause() {
        super.onPause();
        CookieManager.getInstance().flush();
    }

    @Override
    public void onBackPressed() {
        String url = vue.getUrl();
        if (url != null && url.startsWith(HORS_LIGNE)) {
            finish();
        } else if (vue.canGoBack()) {
            vue.goBack();
        } else {
            super.onBackPressed();
        }
    }

    // ------------------------------------------------------------------ PC relié

    private String hote() {
        return prefs.getString("hote", "");
    }

    private String adressePc() {
        return "http://" + hote() + "/";
    }

    private void ouvrirDepart() {
        if (hote().isEmpty()) {
            vue.loadUrl(ACCUEIL);
        } else {
            vue.loadUrl(adressePc());
        }
    }

    /** Lien allmystats://relier?h=IP:PORT&c=CODE (QR code du PC). */
    private boolean traiterLien(Intent intent) {
        if (intent == null || intent.getData() == null) return false;
        Uri u = intent.getData();
        if (!"allmystats".equals(u.getScheme())) return false;
        String h = u.getQueryParameter("h"), c = u.getQueryParameter("c");
        if (h == null || c == null) return false;
        relier(h, c);
        return true;
    }

    private void montrerMessage(final String texte) {
        principal.post(() -> {
            if (vue.getUrl() == null || !vue.getUrl().startsWith(ACCUEIL)) vue.loadUrl(ACCUEIL);
            principal.postDelayed(() -> vue.evaluateJavascript(
                    "window.afficherMessage && afficherMessage(" + JSONObject.quote(texte) + ")", null), 400);
        });
    }

    /** Vérifie l'adresse et le code auprès d'AllMyStats sur le PC, garde le jeton, puis ouvre tes stats. */
    private void relier(String hoteBrut, String codeBrut) {
        final String h = hoteBrut.trim().replaceFirst("^https?://", "").replaceAll("/.*$", "");
        final String hoteComplet = h.contains(":") ? h : h + ":8790";
        final String code = codeBrut.trim().toUpperCase().replace("-", "").replace(" ", "");
        new Thread(() -> {
            HttpURLConnection cnx = null;
            try {
                URL url = new URL("http://" + hoteComplet + "/relier?c=" + Uri.encode(code));
                cnx = (HttpURLConnection) url.openConnection();
                cnx.setInstanceFollowRedirects(false);
                cnx.setConnectTimeout(5000);
                cnx.setReadTimeout(8000);
                int statut = cnx.getResponseCode();
                if (statut == 302) {
                    Map<String, List<String>> entetes = cnx.getHeaderFields();
                    CookieManager cm = CookieManager.getInstance();
                    for (Map.Entry<String, List<String>> e : entetes.entrySet()) {
                        if (e.getKey() != null && e.getKey().equalsIgnoreCase("Set-Cookie")) {
                            for (String cookie : e.getValue()) cm.setCookie("http://" + hoteComplet, cookie);
                        }
                    }
                    cm.flush();
                    prefs.edit().putString("hote", hoteComplet).apply();
                    principal.post(() -> {
                        vue.clearHistory();
                        vue.loadUrl("http://" + hoteComplet + "/");
                    });
                } else if (statut == 403) {
                    montrerMessage("Code incorrect. Regarde le code dans AllMyStats sur ton PC : Paramètres > Téléphone.");
                } else if (statut == 429) {
                    montrerMessage("Trop d'essais : attends 10 minutes puis réessaie.");
                } else {
                    montrerMessage("Ce n'est pas AllMyStats qui a répondu (code " + statut + "). Vérifie l'adresse.");
                }
            } catch (Exception e) {
                montrerMessage("Ton PC ne répond pas à l'adresse " + hoteComplet + ". Vérifie qu'il est allumé, "
                        + "qu'AllMyStats est lancé avec « Téléphone » activé, et que le téléphone est sur le même Wi-Fi.");
            } finally {
                if (cnx != null) cnx.disconnect();
            }
        }).start();
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
        public String pcRelie() {
            return hote();
        }

        @JavascriptInterface
        public void reessayer() {
            principal.post(MainActivity.this::ouvrirDepart);
        }

        @JavascriptInterface
        public void oublierPc() {
            prefs.edit().remove("hote").apply();
            CookieManager.getInstance().removeAllCookies(null);
            principal.post(() -> {
                vue.clearHistory();
                vue.loadUrl(ACCUEIL);
            });
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
                Intent i = new Intent(Intent.ACTION_VIEW, u);
                traiterLien(i);
                return true;
            }
            if (!hote().isEmpty() && ("http".equals(u.getScheme())) && hote().equals(u.getAuthority())) {
                return false;   // AllMyStats du PC : on reste dans l'appli
            }
            // Tout le reste (sites des jeux, Genshin-Builds, cartes…) : dans le navigateur du téléphone
            try {
                startActivity(new Intent(Intent.ACTION_VIEW, u));
            } catch (ActivityNotFoundException e) {
                // pas de navigateur : on ne fait rien
            }
            return true;
        }

        @Override
        public void onReceivedError(WebView v, WebResourceRequest req, WebResourceError err) {
            if (req.isForMainFrame() && !req.getUrl().toString().startsWith("file:")) {
                v.loadUrl(HORS_LIGNE);
            }
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
    protected void onActivityResult(int demande, int resultat, Intent donnees) {
        if (demande == CHOIX_FICHIER && rappelFichier != null) {
            rappelFichier.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultat, donnees));
            rappelFichier = null;
            return;
        }
        super.onActivityResult(demande, resultat, donnees);
    }
}
