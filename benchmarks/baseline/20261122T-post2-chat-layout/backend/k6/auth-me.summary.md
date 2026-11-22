# k6 summary

scenario: me

- http_req_connecting: p(99)=0.044, avg=0.002, min=0.000, med=0.000, max=0.082, p(90)=0.000, p(95)=0.000
- http_req_receiving: p(90)=0.169, p(95)=0.184, p(99)=0.213, avg=0.112, min=0.027, med=0.115, max=0.236
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- http_req_blocked: p(90)=0.015, p(95)=0.017, p(99)=0.068, avg=0.014, min=0.004, med=0.011, max=0.110
- http_req_duration: p(99)=10.121, avg=7.730, min=1.847, med=8.433, max=10.180, p(90)=9.935, p(95)=10.022
- http_req_duration{expected_response:true}: min=1.847, med=8.433, max=10.180, p(90)=9.935, p(95)=10.022, p(99)=10.121, avg=7.730
- http_req_failed: rate=0.000
- iterations: count=48.000, rate=4.789
- http_req_waiting: med=8.264, max=9.908, p(90)=9.790, p(95)=9.822, p(99)=9.902, avg=7.577, min=1.801
- vus: min=1.000, max=1.000
- http_req_sending: avg=0.041, min=0.012, med=0.041, max=0.063, p(90)=0.048, p(95)=0.053, p(99)=0.061
