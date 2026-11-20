# k6 summary

scenario: enrollments

- http_req_sending: max=0.059, p(90)=0.051, p(95)=0.058, p(99)=0.059, avg=0.038, min=0.011, med=0.041
- http_req_failed: rate=0.000
- http_req_connecting: min=0.000, med=0.000, max=0.136, p(90)=0.000, p(95)=0.007, p(99)=0.110, avg=0.007
- iterations: count=20.000, rate=4.870
- http_req_blocked: avg=0.022, min=0.003, med=0.011, max=0.260, p(90)=0.014, p(95)=0.027, p(99)=0.213
- http_req_duration{expected_response:true}: avg=4.193, min=1.268, med=4.885, max=5.232, p(90)=5.151, p(95)=5.179, p(99)=5.221
- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- http_req_waiting: med=4.676, max=5.034, p(90)=4.931, p(95)=4.987, p(99)=5.024, avg=4.006, min=1.203
- vus: min=1.000, max=1.000
- http_req_receiving: max=0.301, p(90)=0.238, p(95)=0.264, p(99)=0.294, avg=0.150, min=0.032, med=0.147
- http_req_duration: avg=4.193, min=1.268, med=4.885, max=5.232, p(90)=5.151, p(95)=5.179, p(99)=5.221
