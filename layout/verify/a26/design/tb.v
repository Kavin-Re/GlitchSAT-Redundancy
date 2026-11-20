module tb; reg clk=0,rst_n=0,en=1,clr=0; reg [7:0] a,b; wire m,f;
ct_cmp d(clk,rst_n,en,clr,a,b,m,f); always #5 clk=~clk;
initial begin #12 rst_n=1; a=8'h5a;b=8'h5a; #10 $display("eq match=%b fault=%b",m,f);
 b=8'h5b; #10 $display("ne match=%b fault=%b",m,f); $finish; end endmodule
