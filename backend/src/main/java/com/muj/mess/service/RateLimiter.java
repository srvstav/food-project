package com.muj.mess.service;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.HashMap;
import java.util.Map;

/**
 * Allows at most `limit` tries per caller within `windowMillis`. Kept in memory, so it resets on restart.
 * OOP: Encapsulation — the map of tries is private; the only way in is tryAcquire().
 * OOP: synchronized — many requests run at once (threads); only one may change the map at a time.
 */
public class RateLimiter {

    private final int limit;
    private final long windowMillis;
    private final Map<String, Deque<Long>> tries = new HashMap<>();

    public RateLimiter(int limit, long windowMillis) {
        this.limit = limit;
        this.windowMillis = windowMillis;
    }

    /** True if this caller may try now (and counts the try); false if they've used up the window. */
    public synchronized boolean tryAcquire(String caller) {
        long now = System.currentTimeMillis();
        Deque<Long> recent = tries.computeIfAbsent(caller, k -> new ArrayDeque<>());
        while (!recent.isEmpty() && now - recent.peekFirst() > windowMillis) {
            recent.pollFirst(); // forget tries older than the window
        }
        if (recent.size() >= limit) return false;
        recent.addLast(now);
        return true;
    }
}
