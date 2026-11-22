# k6 summary

scenario: add_students

- http_req_sending: avg=0.058, min=0.032, med=0.055, max=0.082, p(90)=0.074, p(95)=0.078, p(99)=0.081
- http_req_receiving: p(95)=0.260, p(99)=0.323, avg=0.128, min=0.033, med=0.096, max=0.339, p(90)=0.181
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- http_req_blocked: p(99)=0.138, avg=0.024, min=0.005, med=0.011, max=0.150, p(90)=0.025, p(95)=0.088
- http_req_duration: p(99)=18.190, avg=15.146, min=3.805, med=16.879, max=18.297, p(90)=17.236, p(95)=17.766
- iterations: count=10.000, rate=4.623
- http_req_connecting: p(95)=0.059, p(99)=0.097, avg=0.011, min=0.000, med=0.000, max=0.107, p(90)=0.011
- http_req_duration{expected_response:true}: avg=15.146, min=3.805, med=16.879, max=18.297, p(90)=17.236, p(95)=17.766, p(99)=18.190
- vus: min=1.000, max=1.000
- http_req_failed: rate=0.000
- http_req_waiting: min=3.740, med=16.680, max=18.163, p(90)=17.103, p(95)=17.633, p(99)=18.057, avg=14.961
