# k6 summary

scenario: outline

- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_failed: rate=0.000
- http_req_waiting: p(90)=14.882, p(95)=15.451, p(99)=55.249, avg=10.534, min=2.231, med=9.629, max=57.818
- http_req_duration: avg=10.729, min=2.297, med=9.841, max=57.927, p(90)=15.187, p(95)=15.721, p(99)=55.354
- http_req_duration{expected_response:true}: p(90)=15.187, p(95)=15.721, p(99)=55.354, avg=10.729, min=2.297, med=9.841, max=57.927
- http_req_blocked: min=0.002, med=0.011, max=0.122, p(90)=0.013, p(95)=0.015, p(99)=0.104, avg=0.013
- http_req_connecting: avg=0.002, min=0.000, med=0.000, max=0.091, p(90)=0.000, p(95)=0.000, p(99)=0.082
- http_req_receiving: min=0.030, med=0.147, max=0.785, p(90)=0.255, p(95)=0.297, p(99)=0.632, avg=0.158
- vus: min=5.000, max=5.000
- iterations: rate=23.539, count=238.000
- http_req_sending: min=0.007, med=0.039, max=0.140, p(90)=0.047, p(95)=0.054, p(99)=0.065, avg=0.038
