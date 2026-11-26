package com.phoneagent.app;

import android.content.Context;

import java.io.File;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * Keep the last uncaught exception on disk.
 *
 * A crash inside the agent used to leave nothing behind but a logcat buffer,
 * which is why a CalledFromWrongThreadException in append() had to be reported
 * by a user with a terminal. One file, written before the process dies, is
 * enough to say what happened the next time the app starts.
 */
final class CrashLog {

    private static final String FILE = "last-crash.txt";

    private CrashLog() {
    }

    static void install(Context context) {
        Context app = context.getApplicationContext();
        Thread.UncaughtExceptionHandler previous = Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler((thread, error) -> {
            write(app, thread, error);
            if (previous != null) {
                previous.uncaughtException(thread, error);
            }
        });
    }

    private static void write(Context context, Thread thread, Throwable error) {
        try {
            StringWriter buffer = new StringWriter();
            buffer.write(new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US)
                    .format(new Date()) + "  " + thread.getName() + "\n");
            error.printStackTrace(new PrintWriter(buffer));
            Files.write(new File(context.getFilesDir(), FILE).toPath(),
                    buffer.toString().getBytes(StandardCharsets.UTF_8));
        } catch (Throwable ignored) {
            // the process is already dying; nothing here can save it
        }
    }

    /** The first lines of the last crash, or "" when there is nothing to say. */
    static String last(Context context) {
        try {
            File file = new File(context.getFilesDir(), FILE);
            if (!file.exists()) {
                return "";
            }
            String text = new String(Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8);
            //noinspection ResultOfMethodCallIgnored
            file.delete();
            String[] lines = text.split("\n");
            StringBuilder head = new StringBuilder();
            for (String line : lines) {
                if (head.length() > 160) {
                    break;
                }
                head.append(head.length() > 0 ? "\n" : "").append(line.trim());
            }
            return head.toString();
        } catch (Throwable ignored) {
            return "";
        }
    }
}
