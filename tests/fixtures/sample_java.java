package com.example;

/**
 * A sample class for testing PageIndex Java parser.
 */
import java.util.List;
import java.util.ArrayList;

public class Sample {

    private int value;

    public Sample(int value) {
        this.value = value;
    }

    /**
     * Processing method.
     * @return a result string
     */
    public String process() {
        return "Processed: " + value;
    }
}

enum Status {
    ACTIVE,
    INACTIVE
}

interface Processor {
    void run();
}
