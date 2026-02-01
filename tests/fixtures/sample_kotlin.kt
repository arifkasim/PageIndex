package com.example

import java.util.Date
import java.io.File

/**
 * A sample Kotlin class.
 */
data class User(val name: String, val age: Int)

enum class Role {
    ADMIN, USER
}

interface Service {
    fun execute()
}

object AppConfig {
    const val VERSION = "1.0"
}

/**
 * Main function.
 */
fun main() {
    println("Hello Kotlin")
    val user = User("Alice", 30)
}

class Processor {
    fun process() {
        if (true) {
            println("Processing")
        }
    }
}
