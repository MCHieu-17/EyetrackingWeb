# k6 summary

scenario: outline

- http_req_blocked: max=0.101, p(90)=0.013, p(95)=0.015, p(99)=0.028, avg=0.012, min=0.003, med=0.011
- http_req_duration{expected_response:true}: min=2.099, med=9.632, max=29.343, p(90)=11.337, p(95)=11.545, p(99)=12.534, avg=9.295
- http_req_sending: p(95)=0.059, p(99)=0.083, avg=0.043, min=0.011, med=0.042, max=0.101, p(90)=0.051
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_waiting: med=9.439, max=29.235, p(90)=11.179, p(95)=11.373, p(99)=12.353, avg=9.112, min=2.055
- http_req_duration: max=29.343, p(90)=11.337, p(95)=11.545, p(99)=12.534, avg=9.295, min=2.099, med=9.632
- vus: min=1.000, max=1.000
- http_req_receiving: max=0.292, p(90)=0.221, p(95)=0.234, p(99)=0.290, avg=0.139, min=0.026, med=0.139
- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.001, avg=0.001, min=0.000, med=0.000, max=0.073
- iterations: count=100.000, rate=4.753
- http_req_failed: rate=0.000
