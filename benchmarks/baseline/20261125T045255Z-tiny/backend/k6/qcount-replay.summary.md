# k6 summary

scenario: replay

- http_req_blocked: p(99)=0.115, avg=0.017, min=0.004, med=0.011, max=0.138, p(90)=0.012, p(95)=0.022
- http_req_sending: avg=0.041, min=0.015, med=0.042, max=0.061, p(90)=0.048, p(95)=0.050, p(99)=0.059
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- http_req_duration{expected_response:true}: med=10.622, max=12.403, p(90)=12.206, p(95)=12.219, p(99)=12.366, avg=9.759, min=3.376
- http_req_receiving: med=0.187, max=0.602, p(90)=0.296, p(95)=0.426, p(99)=0.567, avg=0.205, min=0.030
- vus: min=1.000, max=1.000
- http_req_failed: rate=0.000
- http_req_duration: p(99)=12.366, avg=9.759, min=3.376, med=10.622, max=12.403, p(90)=12.206, p(95)=12.219
- iterations: count=20.000, rate=4.743
- http_req_waiting: med=10.404, max=12.147, p(90)=11.931, p(95)=11.996, p(99)=12.117, avg=9.513, min=3.278
- http_req_connecting: max=0.098, p(90)=0.000, p(95)=0.005, p(99)=0.079, avg=0.005, min=0.000, med=0.000
