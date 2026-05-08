#include <verilated.h>
#include <verilated_vcd_c.h>
#include "Vverification_top.h"
#include <cstdlib>

#define CLOCK_PERIOD 20         // 25 MHz -> 40 ns por ciclo
#define SIMULATION_CYCLES 4000  // Número total de ciclos de clock para simulação (default)
#define TARGET_ADDR 60          // Endereço que você quer monitorar
#define TARGET_DATA 5           // Valor que você quer monitorar

int main(int argc, char **argv, char **env) {
        int sim_cycles = SIMULATION_CYCLES;
        if (const char *cycles_env = std::getenv("SIMULATION_CYCLES")) {
            int parsed = std::atoi(cycles_env);
            if (parsed > 0) {
                sim_cycles = parsed;
            }
        }

        const bool trace_all_writes = std::getenv("TRACE_ALL_WRITES") != nullptr;
        const bool trace_all_transactions = std::getenv("TRACE_ALL_TRANSACTIONS") != nullptr;

    Verilated::commandArgs(argc, argv);
    Vverification_top *top = new Vverification_top;
    
    VerilatedVcdC *trace = new VerilatedVcdC;
    Verilated::traceEverOn(true);
    
    top->trace(trace, 100);
    trace->set_time_unit("1ns");  // Define a resolução mínima de 1ns
    trace->open("build/top.vcd");
    
    
    // Inicializa sinais
    top->clk = 0;
    top->rst_n = 0;
    
    // Reset
    int i = 0;
    for (i = 0; i < 10; i++) {
        top->clk = !top->clk;
        top->eval();
        trace->dump(i * CLOCK_PERIOD);
    }
    top->rst_n = 1;
    
    // Simulação
    for (; i < sim_cycles; i++) {
        top->clk = !top->clk;
        top->eval();

        // MONITORAMENTO DE MEMÓRIA
        if (top->cyc && top->stb && trace_all_transactions) {
            printf(
                "BUS:%c,0x%08X,0x%08X,0x%08X,%d\n",
                top->we ? 'W' : 'R',
                top->addr,
                top->data_out,
                top->data_in,
                i
            );
        }

        if (top->cyc && top->stb && top->we) {
            if (trace_all_writes) {
                printf("WRITE:0x%08X,0x%08X,%d\n", top->addr, top->data_out, i);
            }
            if (top->addr == TARGET_ADDR) {
                printf("0x%08X,0x%08X,%d\n",
                            top->addr, top->data_out, i);
            }
        }

        trace->dump(i * CLOCK_PERIOD);
    }
    
    trace->close();
    delete top;
    delete trace;
    return 0;
}
