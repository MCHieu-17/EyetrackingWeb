# k6 summary

scenario: enrollments

- http_req_failed: rate=0.000
- http_req_blocked: min=0.002, med=0.011, max=0.130, p(90)=0.014, p(95)=0.023, p(99)=0.127, avg=0.014
- http_req_receiving: p(90)=0.328, p(95)=0.506, p(99)=0.668, avg=0.181, min=0.014, med=0.151, max=0.727
- http_req_connecting: avg=0.002, min=0.000, med=0.000, max=0.093, p(90)=0.000, p(95)=0.000, p(99)=0.092
- iterations: count=245.000, rate=24.106
- http_req_duration{expected_response:true}: med=5.110, max=26.342, p(90)=8.130, p(95)=8.651, p(99)=22.526, avg=5.742, min=1.034
- http_req_waiting: max=26.250, p(90)=7.595, p(95)=8.375, p(99)=22.062, avg=5.523, min=0.989, med=4.935
- http_req_sending: min=0.006, med=0.039, max=0.131, p(90)=0.047, p(95)=0.051, p(99)=0.085, avg=0.037
- vus: min=5.000, max=5.000
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_duration: avg=5.742, min=1.034, med=5.110, max=26.342, p(90)=8.130, p(95)=8.651, p(99)=22.526
