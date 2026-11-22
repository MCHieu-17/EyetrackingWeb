# k6 summary

scenario: samples

- http_req_receiving: max=0.329, p(90)=0.234, p(95)=0.277, p(99)=0.318, avg=0.130, min=0.054, med=0.109
- http_req_failed: rate=0.000
- http_req_duration: med=20.823, max=24.591, p(90)=24.188, p(95)=24.441, p(99)=24.561, avg=18.302, min=6.065
- http_req_blocked: max=0.108, p(90)=0.015, p(95)=0.025, p(99)=0.092, avg=0.016, min=0.004, med=0.011
- vus: max=1.000, min=1.000
- http_req_duration{expected_response:true}: avg=18.302, min=6.065, med=20.823, max=24.591, p(90)=24.188, p(95)=24.441, p(99)=24.561
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_connecting: med=0.000, max=0.078, p(90)=0.000, p(95)=0.004, p(99)=0.063, avg=0.004, min=0.000
- iterations: count=20.000, rate=4.559
- http_req_waiting: p(90)=24.057, p(95)=24.290, p(99)=24.396, avg=18.129, min=5.952, med=20.611, max=24.423
- http_req_sending: avg=0.043, min=0.014, med=0.043, max=0.069, p(90)=0.052, p(95)=0.053, p(99)=0.066
